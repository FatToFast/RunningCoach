# Frontend AGENTS.md - 프론트엔드 개발 규칙

React + TypeScript 프론트엔드 개발 시 AI 에이전트가 따라야 할 규칙입니다.

---

## 디렉토리 구조

```
frontend/src/
├── pages/                  # 페이지 컴포넌트 (라우트 대응)
│   ├── Dashboard.tsx       # 메인 대시보드
│   ├── Activities.tsx      # 활동 목록
│   ├── ActivityDetail.tsx  # 활동 상세
│   ├── Coach.tsx          # AI 코치 채팅
│   ├── Workouts.tsx       # 워크아웃 관리
│   ├── Trends.tsx         # 트렌드 분석
│   ├── Calendar.tsx       # 캘린더 뷰
│   ├── Gear.tsx           # 장비 관리
│   ├── Strength.tsx       # 근력 운동
│   ├── Records.tsx        # 개인 기록
│   ├── Settings.tsx       # 설정
│   └── Login.tsx          # 로그인
│
├── components/             # 재사용 컴포넌트
│   ├── layout/            # 레이아웃 컴포넌트
│   │   ├── Layout.tsx     # 인증 래퍼 + 사이드바
│   │   ├── Header.tsx     # 상단 헤더
│   │   └── Sidebar.tsx    # 사이드 네비게이션
│   ├── dashboard/         # 대시보드 위젯
│   │   ├── TrainingPacesCard.tsx
│   │   ├── FitnessGauge.tsx
│   │   ├── MileageChart.tsx
│   │   ├── CompactActivities.tsx
│   │   ├── CompactFitness.tsx
│   │   └── ...
│   ├── activity/          # 활동 관련
│   │   ├── ActivityMap.tsx
│   │   └── KmPaceChart.tsx
│   └── common/            # 공통 컴포넌트
│
├── hooks/                  # React Query 커스텀 훅
│   ├── useAuth.ts         # 인증
│   ├── useDashboard.ts    # 대시보드 데이터
│   ├── useActivities.ts   # 활동 데이터
│   ├── useAI.ts           # AI 대화
│   ├── useWorkouts.ts     # 워크아웃
│   ├── useGear.ts         # 장비
│   └── ...
│
├── api/                    # API 클라이언트
│   ├── client.ts          # Axios 인스턴스
│   ├── auth.ts            # 인증 API
│   ├── dashboard.ts       # 대시보드 API
│   ├── activities.ts      # 활동 API
│   ├── ai.ts              # AI API
│   └── ...
│
├── types/                  # TypeScript 타입
│   ├── generated/         # OpenAPI 자동 생성
│   │   └── api.ts
│   └── api.ts             # 커스텀 타입
│
├── utils/                  # 유틸리티 함수
│   └── format.ts          # 포맷팅 (시간, 거리, 페이스)
│
├── constants/              # 상수
├── assets/                 # 정적 자산
├── App.tsx                 # 메인 앱 (라우팅)
└── main.tsx               # 엔트리 포인트
```

---

## 필수 규칙

### 1. 컴포넌트 작성

```tsx
// ✅ 올바른 패턴 - 함수형 컴포넌트 + 타입 정의
interface ActivityCardProps {
  activity: Activity;
  onClick?: () => void;
}

export function ActivityCard({ activity, onClick }: ActivityCardProps) {
  return (
    <div onClick={onClick}>
      {activity.name}
    </div>
  );
}

// ❌ 잘못된 패턴 - any 타입, 클래스 컴포넌트
export function ActivityCard({ activity }: any) {
  ...
}
```

### 2. React Query 사용

```tsx
// hooks/에 커스텀 훅 정의
export function useActivities(page: number, filters?: ActivityFilters) {
  return useQuery({
    queryKey: ['activities', page, filters],
    queryFn: () => activitiesApi.getList({ page, ...filters }),
  });
}

// 페이지에서 사용
function ActivitiesPage() {
  const { data, isLoading, error } = useActivities(1);

  if (isLoading) return <Loading />;
  if (error) return <Error error={error} />;

  return <ActivityList activities={data} />;
}
```

### 3. Mutation 후 캐시 무효화

```tsx
// ✅ 올바른 패턴
const mutation = useMutation({
  mutationFn: workoutsApi.create,
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['workouts'] });
  },
});

// ❌ 잘못된 패턴 - 캐시 무효화 누락
const mutation = useMutation({
  mutationFn: workoutsApi.create,
  // onSuccess 없음 → UI가 업데이트되지 않음
});
```

---

## 타입 규칙

### API 타입 동기화

```bash
# Backend 스키마 변경 후 타입 재생성
npm run generate:api
```

### 타입 정의 위치

```typescript
// types/generated/api.ts - OpenAPI에서 자동 생성 (수정 금지)
export interface Activity { ... }

// types/api.ts - 프론트엔드 전용 타입
export interface ActivityWithUI extends Activity {
  isSelected: boolean;
}
```

### Nullable 처리

```tsx
// ✅ 올바른 패턴
interface Props {
  user: User | null;
}

function UserCard({ user }: Props) {
  if (!user) return null;
  return <div>{user.name}</div>;
}

// ❌ 잘못된 패턴 - 옵셔널 체이닝 남용
function UserCard({ user }: Props) {
  return <div>{user?.name}</div>;  // user가 null이면 빈 div 렌더링
}
```

---

## API 클라이언트 패턴

### api/client.ts

```typescript
import axios from 'axios';

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  withCredentials: true,  // 쿠키 인증
});

// 401 응답 시 로그인 페이지로 리다이렉트
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      window.location.href = '/login';
    }
    return Promise.reject(error);
  },
);
```

### 개별 API 모듈

```typescript
// api/activities.ts
export const activitiesApi = {
  getList: (params: ListParams) =>
    api.get<Activity[]>('/api/v1/activities', { params }),

  getDetail: (id: number) =>
    api.get<ActivityDetail>(`/api/v1/activities/${id}`),

  getSamples: (id: number) =>
    api.get<ActivitySample[]>(`/api/v1/activities/${id}/samples`),
};
```

---

## 스타일링 패턴

### Tailwind CSS 사용

```tsx
// ✅ 올바른 패턴 - Tailwind 클래스
<div className="flex items-center gap-4 p-4 bg-white rounded-lg shadow">
  <span className="text-lg font-semibold text-gray-900">{title}</span>
</div>

// ❌ 잘못된 패턴 - 인라인 스타일
<div style={{ display: 'flex', padding: '16px' }}>
  ...
</div>
```

### 조건부 클래스

```tsx
import { cn } from '@/utils/cn';  // clsx + tailwind-merge

<button
  className={cn(
    'px-4 py-2 rounded',
    isActive ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700',
  )}
>
```

---

## 차트 및 시각화

### Recharts 사용

```tsx
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

function MileageChart({ data }: { data: WeeklyMileage[] }) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data}>
        <XAxis dataKey="week" />
        <YAxis />
        <Tooltip />
        <Line type="monotone" dataKey="distance" stroke="#3b82f6" />
      </LineChart>
    </ResponsiveContainer>
  );
}
```

### MapLibre GL 지도

```tsx
import Map, { Source, Layer } from 'react-map-gl/maplibre';

function ActivityMap({ coordinates }: { coordinates: [number, number][] }) {
  return (
    <Map
      initialViewState={{
        longitude: coordinates[0][0],
        latitude: coordinates[0][1],
        zoom: 14,
      }}
      style={{ width: '100%', height: '400px' }}
      mapStyle="https://tiles.openfreemap.org/styles/liberty"
    >
      {/* 경로 레이어 */}
    </Map>
  );
}
```

---

## 자주 발생하는 실수

### 1. 시간 포맷팅 오류

```typescript
// ❌ 잘못된 패턴 - 60초 오버플로우
function formatTime(seconds: number) {
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);  // 59.5 → 60!
  return `${mins}:${secs}`;  // "5:60" 출력
}

// ✅ 올바른 패턴
function formatTime(seconds: number) {
  const totalSeconds = Math.round(seconds);
  const mins = Math.floor(totalSeconds / 60);
  const secs = totalSeconds % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}
```

### 2. 무한 리렌더링

```tsx
// ❌ 잘못된 패턴 - useEffect 의존성
useEffect(() => {
  setData(processData(rawData));
}, [rawData, processData]);  // processData가 매번 새로 생성됨

// ✅ 올바른 패턴
const processedData = useMemo(() => processData(rawData), [rawData]);
```

### 3. 빈 배열 체크

```tsx
// ❌ 잘못된 패턴
if (activities) {
  return <List items={activities} />;  // 빈 배열도 truthy
}

// ✅ 올바른 패턴
if (activities && activities.length > 0) {
  return <List items={activities} />;
}
```

---

## 라우팅

### App.tsx 구조

```tsx
import { Routes, Route } from 'react-router-dom';
import { Layout } from './components/layout/Layout';

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/activities" element={<Activities />} />
        <Route path="/activities/:id" element={<ActivityDetail />} />
        {/* ... */}
      </Route>
    </Routes>
  );
}
```

---

## 테스트 및 빌드

```bash
# 개발 서버
npm run dev

# 타입 체크
npx tsc --noEmit

# 린팅
npm run lint

# 프로덕션 빌드
npm run build

# API 타입 생성
npm run generate:api
```

---

## 환경 변수

```bash
# .env
VITE_API_BASE_URL=http://localhost:8000
VITE_USE_MOCK_DATA=false
```

```typescript
// 사용
const apiUrl = import.meta.env.VITE_API_BASE_URL;
```

---

## 참조

- `types/generated/api.ts` - API 타입 정의
- `hooks/` - 데이터 페칭 패턴
- `../docs/debug-patterns.md` - 버그 패턴 기록
