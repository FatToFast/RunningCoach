"""Runalyze integration service.

Fetches fitness metrics (CTL, ATL, TSB) and other data from Runalyze
via web scraping since the official API doesn't support reading these metrics.
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class RunalyzeMetrics:
    """Runalyze fitness metrics."""

    ctl: Optional[float] = None  # Chronic Training Load (Fitness)
    atl: Optional[float] = None  # Acute Training Load (Fatigue)
    tsb: Optional[float] = None  # Training Stress Balance (Form)
    vo2max: Optional[float] = None
    marathon_shape: Optional[float] = None
    monotony: Optional[float] = None
    training_strain: Optional[float] = None
    acwr: Optional[float] = None  # Acute:Chronic Workload Ratio


class RunalyzeService:
    """Service for fetching data from Runalyze."""

    BASE_URL = "https://runalyze.com"
    LOGIN_URL = f"{BASE_URL}/login"
    DASHBOARD_URL = f"{BASE_URL}/dashboard"
    CALCULATIONS_URL = f"{BASE_URL}/my/statistics/fitness"

    def __init__(self):
        """Initialize Runalyze service."""
        self._session_cookies: Optional[dict] = None
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                follow_redirects=True,
                timeout=30.0,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
        return self._client

    async def _login(self) -> bool:
        """Login to Runalyze and get session cookies.

        Returns:
            True if login successful, False otherwise.
        """
        if not settings.runalyze_username or not settings.runalyze_password:
            logger.warning("Runalyze credentials not configured")
            return False

        try:
            client = await self._get_client()

            # Step 1: Get login page to extract CSRF token
            login_page = await client.get(self.LOGIN_URL)
            if login_page.status_code != 200:
                logger.error(f"Failed to get login page: {login_page.status_code}")
                return False

            # Extract CSRF token
            soup = BeautifulSoup(login_page.text, "html.parser")
            csrf_input = soup.find("input", {"name": "_csrf_token"})
            if not csrf_input:
                logger.error("Could not find CSRF token in login page")
                return False

            csrf_token = csrf_input.get("value", "")

            # Step 2: Submit login form
            login_data = {
                "_username": settings.runalyze_username,
                "_password": settings.runalyze_password,
                "_csrf_token": csrf_token,
            }

            login_response = await client.post(
                self.LOGIN_URL,
                data=login_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            # Check if login was successful (should redirect to dashboard)
            if login_response.status_code == 200:
                # Check if we're on dashboard or still on login page
                if "/login" in str(login_response.url):
                    logger.error("Login failed - still on login page")
                    return False

                self._session_cookies = dict(client.cookies)
                logger.info("Successfully logged in to Runalyze")
                return True

            logger.error(f"Login failed with status: {login_response.status_code}")
            return False

        except Exception as e:
            logger.error(f"Login error: {e}")
            return False

    async def fetch_metrics(self) -> Optional[RunalyzeMetrics]:
        """Fetch fitness metrics from Runalyze.

        Returns:
            RunalyzeMetrics object or None if fetch fails.
        """
        # Try to login if not already logged in
        if not self._session_cookies:
            if not await self._login():
                return None

        try:
            client = await self._get_client()

            # Fetch the fitness/calculations page
            response = await client.get(self.CALCULATIONS_URL)
            if response.status_code != 200:
                logger.error(f"Failed to fetch calculations: {response.status_code}")
                return None

            # Parse the page to extract metrics
            return self._parse_metrics_page(response.text)

        except Exception as e:
            logger.error(f"Error fetching Runalyze metrics: {e}")
            return None

    def _parse_metrics_page(self, html: str) -> Optional[RunalyzeMetrics]:
        """Parse Runalyze fitness page to extract metrics.

        Args:
            html: HTML content of the fitness page.

        Returns:
            RunalyzeMetrics object or None if parsing fails.
        """
        try:
            soup = BeautifulSoup(html, "html.parser")
            metrics = RunalyzeMetrics()

            # Look for CTL/ATL/TSB values
            # Runalyze displays these in specific elements - adjust selectors as needed

            # Try to find values in the statistics panels
            stat_panels = soup.find_all("div", class_="panel-stat")
            for panel in stat_panels:
                label = panel.find("span", class_="label")
                value = panel.find("span", class_="value")
                if label and value:
                    label_text = label.get_text(strip=True).lower()
                    value_text = value.get_text(strip=True)

                    # Extract numeric value
                    num_match = re.search(r"[-+]?\d*\.?\d+", value_text)
                    if num_match:
                        num_value = float(num_match.group())

                        if "ctl" in label_text or "fitness" in label_text:
                            metrics.ctl = num_value
                        elif "atl" in label_text or "fatigue" in label_text:
                            metrics.atl = num_value
                        elif "tsb" in label_text or "form" in label_text:
                            metrics.tsb = num_value
                        elif "vo2max" in label_text:
                            metrics.vo2max = num_value
                        elif "monotony" in label_text:
                            metrics.monotony = num_value
                        elif "marathon" in label_text and "shape" in label_text:
                            metrics.marathon_shape = num_value
                        elif "shape" in label_text:
                            metrics.marathon_shape = num_value

            # Look for data in various page elements
            # Runalyze uses different structures depending on the page version
            for elem in soup.find_all(["div", "span", "td"]):
                text = elem.get_text(strip=True).lower()

                # Marathon Shape percentage (e.g., "98%" or "Marathon Shape: 98%")
                if "marathon" in text and "shape" in text or "marathonform" in text:
                    shape_match = re.search(r"(\d+(?:\.\d+)?)\s*%", elem.get_text(strip=True))
                    if shape_match and metrics.marathon_shape is None:
                        metrics.marathon_shape = float(shape_match.group(1))

                # Effective VO2max
                if "effective" in text and "vo2" in text:
                    vo2_match = re.search(r"(\d+(?:\.\d+)?)", elem.get_text(strip=True))
                    if vo2_match and metrics.vo2max is None:
                        metrics.vo2max = float(vo2_match.group(1))

            # Alternative: Look for data in JSON embedded in page
            scripts = soup.find_all("script")
            for script in scripts:
                script_text = script.string or ""

                # Look for CTL value
                ctl_match = re.search(r'"ctl"\s*:\s*([\d.]+)', script_text)
                if ctl_match and not metrics.ctl:
                    metrics.ctl = float(ctl_match.group(1))

                # Look for ATL value
                atl_match = re.search(r'"atl"\s*:\s*([\d.]+)', script_text)
                if atl_match and not metrics.atl:
                    metrics.atl = float(atl_match.group(1))

                # Look for TSB value
                tsb_match = re.search(r'"tsb"\s*:\s*([-\d.]+)', script_text)
                if tsb_match and not metrics.tsb:
                    metrics.tsb = float(tsb_match.group(1))

                # Look for VO2max (various formats)
                for pattern in [r'"vo2max"\s*:\s*([\d.]+)', r'"effectiveVo2max"\s*:\s*([\d.]+)',
                               r'"effective_vo2max"\s*:\s*([\d.]+)']:
                    vo2_match = re.search(pattern, script_text)
                    if vo2_match and not metrics.vo2max:
                        metrics.vo2max = float(vo2_match.group(1))
                        break

                # Look for Marathon Shape
                for pattern in [r'"marathonShape"\s*:\s*([\d.]+)', r'"marathon_shape"\s*:\s*([\d.]+)',
                               r'"shape"\s*:\s*([\d.]+)']:
                    shape_match = re.search(pattern, script_text)
                    if shape_match and not metrics.marathon_shape:
                        metrics.marathon_shape = float(shape_match.group(1))
                        break

                # Look for ACWR (Acute:Chronic Workload Ratio)
                acwr_match = re.search(r'"acwr"\s*:\s*([\d.]+)', script_text)
                if acwr_match and not metrics.acwr:
                    metrics.acwr = float(acwr_match.group(1))

                # Look for monotony
                monotony_match = re.search(r'"monotony"\s*:\s*([\d.]+)', script_text)
                if monotony_match and not metrics.monotony:
                    metrics.monotony = float(monotony_match.group(1))

                # Look for training strain
                strain_match = re.search(r'"trainingStrain"\s*:\s*([\d.]+)', script_text)
                if strain_match and not metrics.training_strain:
                    metrics.training_strain = float(strain_match.group(1))

            # Calculate TSB if we have CTL and ATL but no TSB
            if metrics.ctl is not None and metrics.atl is not None and metrics.tsb is None:
                metrics.tsb = metrics.ctl - metrics.atl

            # Log what we found
            logger.info(
                f"Parsed Runalyze metrics: CTL={metrics.ctl}, ATL={metrics.atl}, "
                f"TSB={metrics.tsb}, VO2max={metrics.vo2max}, Shape={metrics.marathon_shape}, "
                f"ACWR={metrics.acwr}"
            )

            return metrics

        except Exception as e:
            logger.error(f"Error parsing Runalyze metrics page: {e}")
            return None

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


# Singleton instance
_runalyze_service: Optional[RunalyzeService] = None


def get_runalyze_service() -> RunalyzeService:
    """Get Runalyze service singleton."""
    global _runalyze_service
    if _runalyze_service is None:
        _runalyze_service = RunalyzeService()
    return _runalyze_service


async def fetch_runalyze_metrics() -> Optional[RunalyzeMetrics]:
    """Convenience function to fetch Runalyze metrics.

    Returns:
        RunalyzeMetrics object or None if fetch fails.
    """
    service = get_runalyze_service()
    return await service.fetch_metrics()
