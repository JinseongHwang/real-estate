# 멀티에이전트 워크플로 가이드

이 스킬의 본조사는 Workflow 도구로 실행한다. 아래 예시 스크립트를 이번 대상에 맞게 고쳐 쓴다.
스크립트는 매번 새로 작성한다. 고정 스크립트를 돌리는 것이 아니라, 정찰 결과에 따라 편성과 임무를 조정한다.

## 1. 편성 원칙

- 파이프라인 구조: `전문 조사(병렬) + 단지 프로필 조사(병렬) → 영역별 교차 검증 (프로필은 제외) → Bull/Bear 대심 + 단지별 정리 + 완결성 감사 → 최종 판단`
- 전문 조사와 교차 검증은 pipeline으로 묶는다. 한 영역의 조사가 끝나면 다른 영역을 기다리지 않고 바로 그 영역을 검증한다.
- 단지 프로필 조사는 영역 조사와 같은 단계에서 병렬로 돈다. 대표 단지를 최대 4개씩 고르게 묶어 에이전트 하나가 맡는다.
  프로필은 교차 검증을 거치지 않는다. 완결성 감사관이 시세 영역 수치와 대조하는 것이 유일한 검증이다.
- 종합 단계(Bull/Bear/단지별 정리/감사/최종판단)는 모든 영역 결과가 필요하므로 배리어가 정당하다.
- 기본 규모: 전문가 7~9명 + 프로필 1~3명 + 검증 최대 각 1명 + 종합 5명. 합계 18~24개 안팎.
  "가볍게" 요청이면 전문가 4~5명, 프로필 1명(대표 단지 3~4개)으로 줄이고, "철저히" 요청이면 검증과 전문가를 늘린다.

### 두 개의 축: 영역별 × 단지별

리포트는 두 축으로 읽혀야 한다. "이 동네의 교통은 어떤가"(영역별)와 "이 단지는 어떤가"(단지별)다.
영역별 조사만 하면 한 단지를 이해하려고 교통, 교육, 시세, 리스크 섹션을 각각 뒤져야 한다. 그래서 두 장치를 둔다.

1. 모든 발견에 `complex` 태그. 특정 단지에만 해당하는 발견은 `args.complexes`의 정식 명칭을 붙인다. 리포트 작성 때 단지별로 다시 모은다.
2. 단지 프로필 조사원. 대표 단지마다 건축 개요, 평형별 실거래, 전세, 역·학교 거리, 상품성, 특이사항을 한 스키마로 수집한다.

`args.complexes`는 STEP 3 정찰에서 오케스트레이터가 확정한다 (선정 기준은 research-framework.md "대표 단지 선정" 절).
candidate 모드에서 후보가 아직 없으면 빈 배열로 넘기고, 스크립트의 후보 발굴 선행 블록이 채운다.

### 모델 라우팅

토큰 비용의 대부분은 검색을 수행하는 수집 병력에서 나온다. "수집은 내리고 판단은 유지"가 기본 전략이다.

| 단계 | model 지정 | 이유 |
|---|---|---|
| 전문 조사 | `'sonnet'` | 검색, 수집, 구조화 중심. 개수가 가장 많아 비용 대부분을 차지한다 |
| 단지 프로필 조사 | `'sonnet'` | 단지별 공부/실거래 수집. 전문 조사와 같은 성격 |
| 교차 검증 | `'sonnet'` | 독립 출처 재검색 중심 |
| 완결성 감사 | `'sonnet'` | digest를 프레임워크와 대조하는 작업 |
| Bull / Bear | 지정 안 함 (세션 모델 상속) | 논증 품질이 리포트의 핵심이다 |
| 단지별 정리 | 지정 안 함 (세션 모델 상속) | 단지마다 장단점과 적합한 매수자를 판단하는 작업 |
| 최종 판단 | 지정 안 함 (세션 모델 상속) | 가장 어려운 종합 판단. 세션에서 가장 좋은 모델이 맡는다 |

- 판단 계층에 특정 상위 모델(opus 등)을 하드코딩하지 않는다. 세션 모델을 상속하면 사용자가 세션에서 고른 등급이 곧 판단 품질이 되고, 계정에 없는 모델을 지정해 실패할 위험도 없다.
- "가볍게" 요청에는 모델을 내리지 말고 인원을 줄여서 대응해라. haiku는 웹 리서치 품질이 흔들리므로 수집 병력으로 쓰지 않는다.
- "철저히" 요청이면 교차 검증의 model 지정을 지워 세션 모델로 격상하는 것을 검토해라.

## 2. 기본 로스터

| key | 역할 | 포함 조건 |
|---|---|---|
| `location` | 입지/교통 | 항상 |
| `infra` | 생활 인프라 | 항상 |
| `education` | 교육/학군 | 항상 (교육 무관 대상이면 축소 가능) |
| `price` | 시세/실거래 | 항상 |
| `develop` | 정비사업/개발 | 항상 (정비 밀집 지역이면 임무 확대) |
| `risk` | 리스크 (악마의 변호인) | 항상 |
| `news` | 뉴스/여론 | 항상 |
| `product` | 단지 상품성 (대상 단지 심층) | `complex` 모드 |
| `comps` | 비교 단지 / 후보 발굴 | `complex`, `candidate`, `compare` 모드 |
| `supply` | 공급/입주 물량 | `scenario` 모드 또는 공급 이슈 지역 |
| `profile:N` | 단지 프로필 (대표 단지 최대 4개씩) | 항상. `args.complexes`를 최대 4개씩 고르게 나눠 N명 편성 |
| (동적 추가) | 재해 특화, 인구/수요, 특정 사업 전담 등 | 정찰에서 발견된 특수 이슈 |

`profile`과 `product`의 차이: `product`는 complex 모드에서 대상 단지 하나를 깊게 파고(대지지분, 관리비, 리모델링 가능성까지),
`profile`은 모든 모드에서 대표 단지 여러 개를 같은 폭으로 얕고 고르게 훑는다. complex 모드에서는 대상 단지도 `profile`에 포함시켜
비교 단지와 같은 포맷의 카드를 갖게 한다.

정찰 결과에 따라 임무 문구에 지역 고유 내용을 넣는다. 예를 들어 방배동이면 develop 임무에
"방배 5/6/7구역 등 주요 재건축 구역별 단계"를 명시하고, 업무지구는 강남/서초 중심으로 잡는다.

## 3. 예시 스크립트 (region 모드 기준)

아래를 복사한 뒤 (1) SPECIALISTS의 임무를 대상에 맞게 수정하고 (2) 모드별 전문가를 넣고 빼서 제출한다.
args는 실제 JSON 값으로 전달한다 (문자열로 감싸지 않는다).

주의: 스크립트 안에서 `Date.now()`, `new Date()`, `Math.random()`은 쓸 수 없다. 기준일은 args.asOf로 받는다.

```js
export const meta = {
  name: 'online-imjang',
  description: '온라인 임장 멀티에이전트 조사',
  phases: [
    { title: '전문 조사', detail: '영역별 전문가와 단지 프로필 병렬 리서치', model: 'sonnet' },
    { title: '교차 검증', detail: '핵심 주장 반박 시도와 재확인', model: 'sonnet' },
    { title: '종합', detail: 'Bull/Bear 대심, 단지별 정리, 완결성 감사, 최종 판단' },
  ],
}

// args: { target, address, mode, asOf, skillDir, traits, purposeHint, budgetHint, complexes }
// complexes: 정찰에서 확정한 대표 단지 목록. [{ name, note }] 형태.
//   name은 모든 에이전트와 리포트가 공유하는 유일한 키다. 서로 달라야 한다. 동 묶음(블록)을 나누면 name 자체를 다르게 쓴다
//   (예. "박석고개1단지 (116~131동)", "박석고개1단지 (101~111동)"). note는 선정 이유("조사 대상", "역세권 대표" 등)이고 매칭에 쓰지 않는다.
//   candidate 모드에서 후보가 아직 없으면 빈 배열로 넘긴다. 아래 "후보 발굴 선행" 블록이 채운다.
const T = args
const DIR = T.skillDir
let COMPLEXES = (T.complexes || []).map(c => (typeof c === 'string' ? { name: c, note: '' } : c))

const SOURCE = {
  type: 'object', required: ['name', 'url', 'grade'],
  properties: {
    name: { type: 'string', description: '기관/서비스명' },
    title: { type: 'string', description: '자료명' },
    url: { type: 'string', description: '실제로 확인한 URL만' },
    grade: { enum: ['A', 'B', 'C', 'D', 'E'], description: 'A 공공원문, B 공공기반 서비스, C 주요 언론, D 민간 부동산 서비스, E 커뮤니티/블로그' },
    date: { type: 'string', description: '자료 기준일 또는 열람일 YYYY-MM-DD' },
  },
}

const FINDING = {
  type: 'object', required: ['claim', 'kind', 'status', 'category', 'critical', 'sources'],
  properties: {
    claim: { type: 'string', description: '한 문장 주장' },
    kind: { enum: ['fact', 'interpretation', 'hypothesis'] },
    status: { enum: ['확정', '높은 신뢰', '참고', '추정', '확인 필요'] },
    category: { type: 'string', description: '입지/교통/교육/인프라/시세/정비사업/리스크 등' },
    figure: { type: 'string', description: '핵심 수치 원문. 없으면 생략' },
    as_of: { type: 'string', description: '수치의 기준 시점' },
    critical: { type: 'boolean', description: '매수 판단을 좌우하면 true' },
    complex: { type: 'string', description: '특정 단지에만 해당하는 발견이면 대표 단지 목록의 정식 명칭 그대로. 지역 전체에 해당하면 생략' },
    sources: { type: 'array', items: SOURCE },
  },
}

const TRADE = {
  type: 'object', required: ['date', 'area', 'price', 'kind'],
  properties: {
    date: { type: 'string', description: '실거래는 계약 연월 YYYY-MM, 호가는 확인일 YYYY-MM-DD' },
    area: { type: 'string', description: '전용면적 ㎡ (평형 병기 가능)' },
    floor: { type: 'string' },
    price: { type: 'string', description: '원문 표기 그대로 (예. 12억 500만)' },
    kind: { enum: ['실거래', '호가', '추정'], description: '실거래와 호가를 절대 섞지 마라' },
    note: { type: 'string', description: '신고가, 직거래, 취소 등' },
  },
}

// 단지 프로필: 대표 단지 하나를 같은 폭으로 훑는 고정 포맷. 리포트의 "단지별 보기" 카드가 이 스키마를 그대로 쓴다.
const COMPLEX_PROFILE = {
  type: 'object', required: ['name', 'status', 'sources'],
  properties: {
    name: { type: 'string', description: '대표 단지 목록의 정식 명칭 그대로' },
    block: { type: 'string', description: '동/블록 구분이 의미 있으면 (예. 116~131동)' },
    address: { type: 'string' },
    built: { type: 'string', description: '준공 연월과 연차' },
    households: { type: 'string', description: '세대수와 동 수' },
    unit_types: { type: 'string', description: '평형 구성 (전용 ㎡ 기준, 주력 평형 표시)' },
    far: { type: 'string', description: '용적률 / 건폐율. 건축물대장 등 공부 기반이면 명시' },
    parking: { type: 'string', description: '세대당 주차대수' },
    builder: { type: 'string', description: '시공사 / 브랜드' },
    structure: { type: 'string', description: '복도식/계단식, 판상형/타워형, 난방 방식' },
    station: { type: 'string', description: '가장 가까운 역과 실제 보행 동선 기준 도보 분. 경사가 있으면 기록' },
    elementary: { type: 'string', description: '배정 초등학교. 학구도 공식 확인인지 민간 서비스 표기인지 명시' },
    trades: { type: 'array', items: TRADE, description: '주력 평형 최근 실거래 3~6건 + 현재 호가 범위 1건' },
    peak: { type: 'string', description: '과거 최고가와 시점, 최근 실거래의 최고가 대비 수준' },
    jeonse: { type: 'string', description: '주력 평형 최근 전세 실거래와 전세가율 (기준 시점 명시)' },
    redevelopment: { type: 'string', description: '정비사업/리모델링 관련 사항과 단계. 없으면 "해당 없음"' },
    highlights: { type: 'array', items: { type: 'string' }, description: '이 단지만의 장점 (근거 포함)' },
    drawbacks: { type: 'array', items: { type: 'string' }, description: '이 단지만의 단점 (근거 포함). highlights와 비슷한 개수로' },
    status: { enum: ['확정', '높은 신뢰', '참고', '추정', '확인 필요'], description: '프로필 전체의 신뢰 수준' },
    unresolved: { type: 'array', items: { type: 'string' }, description: '온라인으로 확인하지 못한 항목' },
    sources: { type: 'array', items: SOURCE },
  },
}

const PROFILES = {
  type: 'object', required: ['profiles'],
  properties: { profiles: { type: 'array', items: COMPLEX_PROFILE } },
}

const REPORT = {
  type: 'object', required: ['summary', 'findings', 'unresolved', 'field_check'],
  properties: {
    summary: { type: 'string', description: '이 영역의 조사 결론 3~5문장' },
    findings: { type: 'array', items: FINDING },
    unresolved: { type: 'array', items: { type: 'string' }, description: '온라인으로 확인하지 못한 것' },
    field_check: { type: 'array', items: { type: 'string' }, description: '현장에서만 확인 가능한 항목' },
  },
}

// candidate 모드 후보 발굴용. REPORT에 후보 목록이 붙는다.
const CANDIDATES = {
  type: 'object', required: ['summary', 'findings', 'unresolved', 'field_check', 'candidates'],
  properties: Object.assign({}, REPORT.properties, {
    candidates: {
      type: 'array', minItems: 3, maxItems: 6,
      items: {
        type: 'object', required: ['name', 'reason'],
        properties: {
          name: { type: 'string', description: '실거래 신고 단지명(정식 명칭). 동 묶음을 나누면 이름에 블록을 포함' },
          reason: { type: 'string', description: '선정 이유 (조건 충족 근거와 수치)' },
        },
      },
    },
  }),
}

const VERDICT = {
  type: 'object', required: ['verdicts'],
  properties: {
    verdicts: {
      type: 'array',
      items: {
        type: 'object', required: ['claim', 'verdict', 'reason'],
        properties: {
          claim: { type: 'string' },
          verdict: { enum: ['유지', '수정', '기각', '판단 불가'] },
          corrected: { type: 'string', description: 'verdict가 수정일 때 고쳐 쓴 주장' },
          reason: { type: 'string' },
          sources: { type: 'array', items: SOURCE },
        },
      },
    },
  },
}

const CASE = {
  type: 'object', required: ['points'],
  properties: {
    points: {
      type: 'array', minItems: 3, maxItems: 7,
      items: {
        type: 'object', required: ['point', 'basis'],
        properties: {
          point: { type: 'string', description: '논거 한 문장' },
          basis: { type: 'string', description: '근거가 된 조사 발견' },
          confidence: { enum: ['강함', '보통', '약함'] },
        },
      },
    },
  },
}

const GAPS = {
  type: 'object', required: ['missing', 'unverified', 'conflicts'],
  properties: {
    missing: { type: 'array', items: { type: 'string' }, description: '조사되지 않은 영역/질문' },
    unverified: { type: 'array', items: { type: 'string' }, description: '검증되지 않은 핵심 주장' },
    conflicts: { type: 'array', items: { type: 'string' }, description: '서로 어긋나는 수치와 내용' },
  },
}

// 단지별 정리: 영역 조사 발견(complex 태그)과 프로필을 단지 단위로 다시 모아 판단한다.
const COMPLEX_VERDICTS = {
  type: 'object', required: ['complexes'],
  properties: {
    complexes: {
      type: 'array',
      items: {
        type: 'object', required: ['name', 'one_line', 'pros', 'cons', 'who_fits', 'price_view'],
        properties: {
          name: { type: 'string', description: '대표 단지 목록의 정식 명칭 그대로' },
          one_line: { type: 'string', description: '이 단지를 한 문장으로. 장점과 한계가 함께 담기게' },
          pros: { type: 'array', maxItems: 5, items: { type: 'string' }, description: '근거 있는 장점. 근거가 없으면 빈 배열로 두고 data_gaps에 이유를 써라' },
          cons: { type: 'array', maxItems: 5, items: { type: 'string' }, description: '근거 있는 단점. pros와 같은 비중. 근거가 없으면 빈 배열' },
          price_view: { type: 'string', description: '절대 가격(최고가 대비)과 상대 가격(대표 단지 내 위치)을 한두 문장으로. 추정이면 명시' },
          who_fits: { type: 'string', description: '어떤 매수자에게 맞고 어떤 매수자에게 맞지 않는지' },
          watch_out: { type: 'array', maxItems: 3, items: { type: 'string' }, description: '이 단지만의 현장 확인 항목' },
          data_gaps: { type: 'array', items: { type: 'string' }, description: '이 단지에 대해 확인 못 한 핵심 정보' },
        },
      },
    },
    pick_by_purpose: {
      type: 'array', maxItems: 4,
      items: {
        type: 'object', required: ['purpose', 'pick', 'reason'],
        properties: {
          purpose: { type: 'string', description: '예. 역세권 실거주 / 예산 우선 / 자녀 교육 / 대형 평형' },
          pick: { type: 'string', description: '그 목적에 가장 맞는 단지 (정식 명칭)' },
          reason: { type: 'string' },
        },
      },
      description: '목적별로 어느 단지가 맞는지. 점수화하지 말고 이유를 써라',
    },
  },
}

const JUDGE = {
  type: 'object',
  required: ['one_line', 'verdict', 'verdict_reasons', 'top_risks', 'key_unknowns', 'who_fits', 'field_focus'],
  properties: {
    one_line: { type: 'string', description: '리포트 최상단에 실을 한 줄 결론' },
    verdict: { enum: ['매수 고려', '적극 검토', '관망', '비추천'] },
    verdict_reasons: { type: 'array', minItems: 3, maxItems: 5, items: { type: 'string' } },
    top_risks: { type: 'array', minItems: 1, maxItems: 3, items: { type: 'string' } },
    key_unknowns: { type: 'array', items: { type: 'string' }, description: '공개 데이터로 확정할 수 없는 핵심 변수' },
    who_fits: { type: 'string', description: '어떤 사람에게 맞고 어떤 사람에게 맞지 않는지' },
    field_focus: { type: 'array', maxItems: 5, items: { type: 'string' }, description: '현장 방문 시 최우선 확인 항목' },
    negotiation_view: { type: 'string', description: '협상 관점 코멘트. 추정임을 명시' },
    complex_pick: { type: 'string', description: '대표 단지 중 어디를 먼저 봐야 하는지와 이유. 단지별 정리의 pick_by_purpose와 어긋나면 그 이유를 써라' },
  },
}

const BASE = [
  '너는 "' + T.target + '" 온라인 임장 조사팀의 일원이다.',
  '조사 대상: ' + T.target + ' (' + T.address + ') / 조사 모드: ' + T.mode + ' / 조사 기준일: ' + T.asOf,
  T.traits ? '정찰에서 파악한 지역 특성: ' + T.traits : '',
  T.purposeHint ? '사용자 목적 단서: ' + T.purposeHint : '',
  T.budgetHint ? '예산 단서: ' + T.budgetHint : '',
  '',
  '시작 전에 반드시 Read 해라: ' + DIR + '/references/source-priority.md, ' + DIR + '/references/verification-guide.md',
  '',
  '공통 규칙:',
  '- WebSearch/WebFetch가 도구 목록에 없으면 ToolSearch("select:WebSearch,WebFetch")로 로드해서 써라.',
  '- 공공기관(A등급) 출처를 먼저 확인하고, 민간 서비스 수치는 출처를 달아 참고로 기록해라.',
  '- 모든 수치에 기준 시점을 붙여라. 못 찾은 것은 지어내지 말고 상태를 "확인 필요"로 남겨라.',
  '- 긍정 정보만 모으지 마라. 반대 증거 검색(단점, 소음, 침수, 문제, 지연)을 최소 1회 수행해라.',
  '- 호가와 실거래가를 구분해라. "개발 예정" 문구는 사업 단계 확인 전에는 호재로 단정하지 마라.',
  '- 특정 단지에만 해당하는 발견은 complex 필드에 대표 단지 목록의 이름을 넣어라. 지역 전체 얘기면 비워라. 목록에 없는 단지는 claim 문장 안에 이름을 쓰되 complex는 비워라.',
  '- sources의 url에는 실제로 열어 확인한 URL만 넣어라.',
  '- 너의 최종 출력은 사람용 문장이 아니라 스키마에 맞는 구조화 데이터다.',
].filter(Boolean).join('\n')

// 후보 발굴 선행 (candidate 모드에서 후보가 아직 없을 때만). 후보가 정해져야 프로필과 단지 태그가 가능하므로 이것만 먼저 단독으로 돈다.
let compsFirst = null
if (T.mode === 'candidate' && !COMPLEXES.length) {
  compsFirst = await agent(
    BASE + '\n\n[역할] 후보 발굴 조사원\n\n[임무]\n조건(예산, 평형, 목적)에 맞는 후보 단지 3~6개를 발굴하고 각각의 최근 실거래, 평당가, 연식, 세대수, 역거리, 전세가율을 수집해라. ' +
    '후보마다 선정 이유를 수치와 함께 밝혀라. candidates의 name은 실거래 신고 단지명으로 써라.',
    { label: '조사:comps', phase: '전문 조사', schema: CANDIDATES, model: 'sonnet' })
  COMPLEXES = ((compsFirst && compsFirst.candidates) || []).map(c => ({ name: c.name, note: c.reason || '' }))
  log('후보 발굴 완료: ' + COMPLEXES.map(c => c.name).join(', '))
}

const COMPLEX_NAMES = COMPLEXES.map(c => c.name)
// 이름 매칭은 공백을 무시한다. 에이전트가 이름을 조금 다르게 적어도 프로필과 발견이 떨어져 나가지 않게 한다.
const norm = s => String(s || '').replace(/\s+/g, '')
const sameComplex = (a, b) => norm(a) === norm(b)

const COMMON = BASE + (COMPLEX_NAMES.length
  ? '\n\n대표 단지 목록. complex 필드와 프로필 name에는 아래 이름을 글자 그대로 써라. 뒤의 메모는 이름이 아니다.\n' +
    COMPLEXES.map(c => '- ' + c.name + (c.note ? '  (메모: ' + c.note + ')' : '')).join('\n')
  : '')

// 전문가 편성. 오케스트레이터가 정찰 결과에 맞게 임무를 수정하고 전문가를 넣고 뺀다.
const SPECIALISTS = [
  {
    key: 'location', title: '입지/교통',
    mission: '지하철역과 노선, 대상 기준 도보 거리와 실제 보행 동선(경사와 언덕, 큰 도로 횡단, 육교), 버스, 주요 업무지구까지의 대중교통과 차량 통근 시간(어느 시간대 기준인지 명시), 도로 접근성과 상습 정체 구간을 조사해라. 직선거리와 실제 동선을 구분하고, 언덕이나 경사가 있으면 반드시 기록해라.',
  },
  {
    key: 'infra', title: '생활 인프라',
    mission: '대형마트, 백화점, 전통시장, 병원(응급실 포함), 약국, 공원, 체육/문화시설, 어린이시설, 주요 상권을 도보 500m / 1km / 2~3km 반경으로 나눠 조사해라. 반경은 지형과 지역 특성에 맞게 조정해라. "가깝다"로 끝내지 말고 실제 이용 편의(도보 동선, 규모, 수준)를 함께 평가해라.',
  },
  {
    key: 'education', title: '교육/학군',
    mission: '배정 초등학교(학구도 기준)와 통학로(거리, 대로 횡단 여부), 중/고등학교와 학군 평판, 학원가 위치와 규모, 학교알리미 기반 학교 정보, 교육환경 변화 가능성(신설/이전/과밀)을 조사해라. "학교가 가깝다"가 아니라 "실제 통학이 편한가"를 판단해라. 배정 정보는 공식 확인이 아니면 "확인 필요"로 표시해라.',
  },
  {
    key: 'price', title: '시세/실거래',
    mission: '최근 실거래가(국토교통부 실거래가 공개시스템 기준)와 거래량, 대표 단지별/평형별 가격과 평당가, 전세가와 전세가율, 과거 최고가 대비 현재 수준, 최근 1~2년 추이, 현재 호가 수준을 조사해라. 실거래/호가/추정가를 반드시 구분하고 각 수치에 기준 시점을 붙여라. 민간 서비스 수치는 공식 실거래와 교차확인해라.',
  },
  {
    key: 'develop', title: '정비사업/개발',
    mission: '해당 지역의 정비사업(재건축, 재개발, 모아타운, 가로주택)과 현재 진행 단계(구역지정~준공 중 어디인지), 교통 개발(신규 노선, 역 신설), 대형 개발(업무/상업시설, 공원, 학교)을 조사해라. 서울이면 정비사업 정보몽땅, 그 외 지역이면 해당 지자체 고시/공고를 우선 확인해라. 각 사업을 "공식 확정/진행(단계 명시)/계획/검토/무산" 중 하나로 분류하고 근거 문서를 남겨라.',
  },
  {
    key: 'risk', title: '리스크',
    mission: '너는 이 팀의 악마의 변호인이다. 단점과 위험만 찾아라. 침수 이력과 저지대 여부(생활안전지도 등), 소음원(철도, 대로, 공사장, 유흥), 유해시설, 고압선, 경사와 언덕, 주차난, 노후 인프라, 학군/상권의 약점, 규제(토지거래허가구역, 용도지역, 고도제한)를 조사해라. 반대 증거 검색("단점", "소음", "침수", "문제")을 반드시 수행해라. 커뮤니티 글은 사실 근거로 쓰지 말고 추가 확인용 키워드 발굴로만 써라.',
  },
  {
    key: 'news', title: '뉴스/여론',
    mission: '최근 2년 안의 뉴스에서 호재(교통, 개발, 정비, 기업, 상업시설)와 악재(지연, 갈등, 무산, 규제, 하락)를 균형 있게 조사해라. 기사마다 "공식 확정/계획/검토/추진/업계 전망/언론 추측"을 구분해라. 제목만 보지 말고 본문과 후속 보도를 확인해라. 커뮤니티 여론은 E등급 참고로만 수집해라.',
  },
  // complex 모드에서 추가:
  // { key: 'product', title: '단지 상품성', mission: '단지 자체를 조사해라. 준공연도, 세대수, 동 수와 배치, 평형 구성, 용적률과 건폐율, 대지지분, 세대당 주차대수, 난방 방식, 관리비 수준, 복도식/계단식, 커뮤니티 시설, 시공사와 브랜드, 재건축 또는 리모델링 가능성과 그 근거(연식, 용적률, 안전진단 여부)를 다뤄라. 건축물대장 등 공부 기반 정보와 민간 서비스 정보를 구분해라.' },
  // complex/compare 모드에서 추가. 비교 단지는 대표 단지 목록으로 고정한다. 여기서 스스로 고르게 하면 비교표(13번)와 단지 카드(14번)가 다른 단지를 다루게 된다.
  // { key: 'comps', title: '비교 단지', mission: '대표 단지 목록의 단지들을 비교 분석해라. 목록 밖의 단지를 새로 고르지 마라 (목록이 왜 그렇게 정해졌는지 의문이 있으면 unresolved에 적어라). 각 단지의 최근 실거래, 평당가, 연식, 세대수, 역거리, 전세가율을 같은 기준으로 수집하고 "왜 가격 차이가 나는가"를 연식, 역거리, 세대수, 학군, 정비 기대감으로 분해해라.' },
  // candidate 모드: 후보 발굴은 위 "후보 발굴 선행" 블록이 맡는다. 여기에 comps를 넣지 마라 (두 번 돈다).
]

log('전문 조사 시작: ' + SPECIALISTS.map(s => s.title).join(', ') + ' / 단지 프로필 ' + COMPLEX_NAMES.length + '개')

// 단지 프로필 조사. 대표 단지를 최대 4개씩 고르게 묶어 병렬로 돌린다. 영역 조사와 동시에 진행되며 서로 기다리지 않는다.
// 프로필은 교차 검증 단계를 거치지 않는다. 완결성 감사관이 시세 영역 수치와 대조하는 것이 유일한 검증이다.
const PROFILE_MISSION =
  '아래 단지 각각에 대해 COMPLEX_PROFILE 스키마의 모든 항목을 같은 폭으로 채워라. 한 단지에 치우치지 마라.\n' +
  '- 건축 개요(준공, 세대수, 동 수, 평형 구성, 용적률, 주차, 시공사)는 건축물대장이나 공공 기반 서비스를 우선하고, 민간 서비스 수치면 출처에 등급을 달아라.\n' +
  '- trades에는 주력 평형의 최근 실거래 3~6건(국토교통부 실거래가 기준)을 넣고, 현재 호가 범위는 kind를 "호가"로 분리해 1건만 넣어라.\n' +
  '- station은 직선거리가 아니라 실제 보행 동선 기준 도보 분이다. 경사, 큰 도로 횡단이 있으면 적어라.\n' +
  '- elementary는 학구도안내서비스 확인이면 "공식", 민간 서비스 표기면 "민간 표기"라고 적어라.\n' +
  '- highlights와 drawbacks는 비슷한 개수로 써라. 단점이 없다고 쓰지 마라. 단점이 안 보이면 반대 증거 검색("<단지명> 단점", "소음", "주차", "하자")을 했는지 다시 확인해라.\n' +
  '- 못 찾은 항목은 비우고 unresolved에 적어라. 지어내지 마라.\n'

const chunks = []
const per = COMPLEXES.length ? Math.ceil(COMPLEXES.length / Math.ceil(COMPLEXES.length / 4)) : 4
for (let i = 0; i < COMPLEXES.length; i += per) chunks.push(COMPLEXES.slice(i, i + per))

const profileTask = parallel(chunks.map((group, i) => () =>
  agent(COMMON + '\n\n[역할] 단지 프로필 조사원 (' + (i + 1) + '/' + chunks.length + ')\n\n[임무]\n' + PROFILE_MISSION +
    '\n[담당 단지] (name에는 이 이름을 글자 그대로 써라)\n' + group.map(c => '- ' + c.name + (c.note ? '  (메모: ' + c.note + ')' : '')).join('\n'),
    { label: '프로필:' + (i + 1), phase: '전문 조사', schema: PROFILES, model: 'sonnet' })
)).then(rs => rs.flatMap(r => (r && r.profiles) || []))

// 영역별 조사가 끝나는 대로 그 영역의 핵심 주장을 교차 검증한다 (영역 간 대기 없음).
const domainResults = await pipeline(
  SPECIALISTS,
  s => agent(COMMON + '\n\n[역할] ' + s.title + ' 전문 조사원\n\n[임무]\n' + s.mission,
    { label: '조사:' + s.key, phase: '전문 조사', schema: REPORT, model: 'sonnet' }),
  (rep, s) => {
    if (!rep) return null
    const critical = (rep.findings || []).filter(f => f.critical).slice(0, 5)
    if (!critical.length) return { key: s.key, title: s.title, report: rep, verified: [] }
    const list = critical.map((f, i) =>
      (i + 1) + '. ' + f.claim +
      (f.figure ? ' [수치: ' + f.figure + ']' : '') +
      ' (원 출처: ' + ((f.sources || []).map(x => x.name + ' ' + x.url).join(' / ') || '없음') + ')').join('\n')
    return agent(
      COMMON + '\n\n[역할] 교차 검증 담당 (' + s.title + ' 영역)\n\n' +
      '아래는 다른 조사원이 "매수 판단을 좌우한다"고 표시한 주장이다. 각 주장을 반박하려고 시도해라.\n' +
      '원 출처와 독립된 다른 출처에서 재확인하고, 원 출처가 오래됐거나 홍보성이거나 이해관계자 자료인지 의심해라.\n' +
      '재확인이 안 되면 억지로 유지하지 말고 "판단 불가"로 판정해라.\n\n' + list,
      { label: '검증:' + s.key, phase: '교차 검증', schema: VERDICT, model: 'sonnet' }
    ).then(v => ({ key: s.key, title: s.title, report: rep, verified: (v && v.verdicts) || [] }))
  }
)

const domains = domainResults.filter(Boolean)
if (compsFirst) domains.push({ key: 'comps', title: '후보 발굴', report: compsFirst, verified: [] })
const profiles = await profileTask

// 종합 단계는 모든 영역 결과가 필요하므로 여기서부터 배리어가 정당하다.
const digest = JSON.stringify(domains.map(d => ({
  영역: d.title,
  요약: d.report.summary,
  발견: (d.report.findings || []).map(f => ({
    주장: f.claim, 구분: f.kind, 상태: f.status, 수치: f.figure || null, 기준일: f.as_of || null, 핵심: f.critical, 단지: f.complex || null,
  })),
  검증결과: d.verified,
  미확인: d.report.unresolved,
})))

// 단지별로 다시 모은 발견. complex 태그가 붙은 것만 단지 아래로 들어간다.
const byComplex = COMPLEX_NAMES.map(name => ({
  단지: name,
  프로필: profiles.find(p => sameComplex(p.name, name)) || null,
  발견: domains.flatMap(d => (d.report.findings || []).filter(f => f.complex && sameComplex(f.complex, name)).map(f => ({
    영역: d.title, 주장: f.claim, 구분: f.kind, 상태: f.status, 수치: f.figure || null, 기준일: f.as_of || null,
  }))),
}))
const complexDigest = JSON.stringify(byComplex)

log('영역 조사 완료. Bull/Bear 대심, 단지별 정리, 완결성 감사를 시작한다')

const CASE_RULES = '조사 결과 digest에 있는 근거만 사용해라. 근거가 부족할 때만 최소한으로 추가 검색해라.\n' +
  '검증에서 "기각" 또는 "판단 불가"가 된 주장은 근거로 쓰지 마라.\n\n[조사 결과 digest]\n' + digest

// Bull/Bear, 단지별 정리, 최종 판단에는 model을 지정하지 않는다. 세션 모델(가장 좋은 등급)을 상속한다.
const [bull, bear, complexVerdicts, gaps] = await parallel([
  () => agent(COMMON + '\n\n[역할] 매수 옹호론자 (Bull)\n"' + T.target + '"을(를) 매수해야 하는 이유를 가장 설득력 있게 구성해라.\n' + CASE_RULES,
    { label: 'Bull', phase: '종합', schema: CASE }),
  () => agent(COMMON + '\n\n[역할] 매수 신중론자 (Bear)\n"' + T.target + '" 매수가 잘못된 선택일 수 있는 이유를 가장 설득력 있게 구성해라.\n' + CASE_RULES,
    { label: 'Bear', phase: '종합', schema: CASE }),
  () => COMPLEX_NAMES.length ? agent(
    COMMON + '\n\n[역할] 단지별 정리 담당\n' +
    '대표 단지 하나하나에 대해 "이 단지는 어떤 집인가"를 정리해라. 영역별 조사 결과를 단지 단위로 다시 읽는 작업이다.\n' +
    '- 프로필과 단지 태그 발견에 있는 근거만 써라. 지역 전체 얘기를 단지 장점으로 복사하지 마라.\n' +
    '- pros와 cons는 같은 비중이다. 근거가 없으면 지어내지 말고 빈 배열로 두고, 그 단지의 data_gaps에 무엇이 없어서 판단을 못 했는지 적어라.\n' +
    '- price_view는 최고가 대비(절대)와 대표 단지 내 위치(상대)를 함께 다뤄라. 비싸다/싸다 단정 대신 왜 그 가격인지 써라.\n' +
    '- pick_by_purpose는 점수가 아니라 이유다. 목적을 3~4개로 나누고 각각 가장 맞는 단지를 골라라.\n' +
    '- 검증에서 "기각" 또는 "판단 불가"가 된 주장은 근거로 쓰지 마라.\n\n' +
    '[단지별 digest]\n' + complexDigest + '\n\n[영역별 digest]\n' + digest,
    { label: '단지별정리', phase: '종합', schema: COMPLEX_VERDICTS }
  ) : null,
  () => agent(COMMON + '\n\n[역할] 완결성 감사관\n조사 결과 digest를 보고 "무엇이 빠졌는가"만 찾아라. 추가 검색은 하지 마라. 조사되지 않은 영역, 검증되지 않은 핵심 주장, 서로 어긋나는 수치를 보고해라.\n' +
    '단지 프로필의 실거래/전세 수치가 시세 영역 조사 수치와 어긋나면 conflicts에 단지명과 함께 적어라. 프로필이 비어 있는 대표 단지는 missing에 적어라.\n\n' +
    '[조사 결과 digest]\n' + digest + '\n\n[단지별 digest]\n' + complexDigest,
    { label: '완결성', phase: '종합', schema: GAPS, model: 'sonnet' }),
])

const judge = await agent(
  COMMON + '\n\n[역할] 수석 애널리스트\n' +
  '아래 Bull/Bear 논거, 단지별 정리, 조사 digest를 종합해 최종 판단을 내려라.\n' +
  '"내가 이 집을 내 돈으로 산다면 무엇 때문에 사고, 무엇 때문에 망설일 것인가"에 답해라.\n' +
  '판단은 "매수 고려/적극 검토/관망/비추천" 중 하나다. 투자 권유 표현은 금지다.\n' +
  '실거주 관점과 자산가치 관점이 다르면 분리해서 서술해라.\n' +
  'complex_pick에는 대표 단지 중 먼저 볼 곳과 이유를 써라.\n\n' +
  '[Bull]\n' + JSON.stringify(bull) + '\n\n[Bear]\n' + JSON.stringify(bear) +
  '\n\n[단지별 정리]\n' + JSON.stringify(complexVerdicts) + '\n\n[조사 결과 digest]\n' + digest,
  { label: '최종판단', phase: '종합', schema: JUDGE }
)

return { asOf: T.asOf, target: T.target, mode: T.mode, complexes: COMPLEX_NAMES, domains, profiles, byComplex, complexVerdicts, bull, bear, gaps, judge }
```

## 4. 모드별 수정 포인트

- `region`: `args.complexes`에 정찰에서 고른 대표 단지 5~10개를 넣는다. 같은 단지라도 역 거리나 실거래 신고 단위가 다른 동 묶음은 name을 다르게("OO단지 (116~131동)") 따로 넣을 수 있다.
- `complex`: `product`, `comps` 전문가를 추가한다. price 임무를 "이 단지의 평형별 실거래 전수"로 좁힌다.
  `args.complexes`에는 대상 단지 + 정찰에서 고른 비교 단지 3~4개를 넣는다. 대상 단지는 note에 "조사 대상"이라고 적는다.
  `comps` 임무는 이 목록의 비교 분석으로 고정한다. 스스로 비교 단지를 고르게 하지 마라 (스크립트의 comps 주석 참고).
- `candidate`: 후보 발굴은 스크립트의 "후보 발굴 선행" 블록이 맡는다. `args.complexes`를 빈 배열로 넘기면 그 블록이 `CANDIDATES` 스키마로 후보 3~6개를 받아 `COMPLEXES`를 채우고,
  그 다음에 영역 전문가와 프로필이 병렬로 돈다. 이 블록의 결과는 `domains`에 "후보 발굴" 영역으로 합류한다. SPECIALISTS에 `comps`를 따로 넣지 마라.
  정찰에서 이미 후보가 뚜렷하면 `args.complexes`에 넣어라. 그러면 선행 블록은 건너뛰고 SPECIALISTS에 compare 모드와 같은 고정 목록 `comps`를 넣는다.
- `compare`: 비교 대상들이 명시돼 있으므로 `args.complexes`에 그대로 넣고, 고정 목록 `comps`를 넣고, price/product를 비교 대상 전체로 확장한다.
- `scenario`: `supply`(입주 예정 물량, 청약홈/지자체 공급계획)와 인구/수요 전문가를 추가하고, judge 프롬프트에 "낙관/기준/비관 시나리오를 구분하되 각 시나리오의 전제(확정 사실인지 가설인지)를 명시해라"를 추가한다.

## 5. 실행 후 처리

- `gaps.missing`과 `gaps.unverified`에서 매수 판단을 좌우하는 항목만 골라 보강 에이전트를 1라운드 띄운다 (Agent 도구로 충분하다).
  `profiles`에 아예 없는 대표 단지는 매수 판단을 좌우하는 구멍으로 본다. 그 단지만 묶어 프로필 보강 에이전트를 띄우고,
  보강이 끝나면 "단지별 정리" 프롬프트를 그 단지만으로 한 번 더 실행해 pros/cons/price_view/who_fits를 새 데이터로 다시 받는다. 데이터 없이 쓴 판단을 새 숫자와 섞지 않는다.
  trades만 비어 있는 단지(거래가 실제로 드문 단지)는 보강 대상이 아니다. 카드에 "최근 거래 없음"으로 남긴다.
- `gaps.conflicts`는 리포트의 해당 섹션에서 충돌 내용과 해석을 명시한다 (verification-guide.md 5절).
  단, 같은 단지·같은 평형·같은 기간의 실거래 수치가 프로필과 시세 영역에서 다르게 나온 경우만은 국토교통부 실거래 원문을 다시 확인해 한 값으로 통일하고, 다른 값이 왜 나왔는지(기간, 취소 거래, 집계 단위)를 한계 섹션에 적는다.
- `byComplex`와 `complexVerdicts`는 리포트의 "단지별 보기" 섹션 원재료다. 단지 카드에 쓰는 수치는 `profiles`에서, 장단점과 적합한 매수자는 `complexVerdicts`에서, 영역별 조사가 단지에 대해 찾아낸 내용은 `byComplex.발견`에서 가져온다.
- 결과가 비어 보이면 워크플로 transcript 디렉토리의 `journal.jsonl`을 읽어 각 agent의 실제 반환값을 확인한다.
- 워크플로가 중간에 죽었으면 같은 scriptPath에 `resumeFromRunId`를 붙여 재개한다. 완료된 조사는 캐시로 즉시 돌아온다.

## 6. Workflow 도구가 없는 환경의 폴백

1. 위 SPECIALISTS의 프롬프트(COMMON + 역할 + 임무)와 단지 프로필 프롬프트(COMMON + PROFILE_MISSION + 담당 단지 3~4개)를 그대로 사용해 Agent(또는 Task) 도구로 병렬 실행한다.
   모델 라우팅도 동일하게 적용한다 (수집/검증은 model 파라미터로 sonnet, 판단부는 지정 없이 상속).
2. 각 결과에서 critical 주장을 뽑아 검증 에이전트를 병렬 실행한다.
3. 발견을 complex 태그로 단지별로 다시 모은 뒤, Bull/Bear/단지별 정리/완결성 에이전트를 병렬 실행하고, 최종 판단 에이전트를 실행한다.
4. 구조화 출력 스키마를 강제할 수 없으므로, 프롬프트에 "위 스키마 형태의 JSON만 반환해라"를 명시하고 반환 JSON을 직접 파싱한다.
