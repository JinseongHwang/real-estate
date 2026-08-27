# 멀티에이전트 워크플로 가이드

이 스킬의 본조사는 Workflow 도구로 실행한다. 아래 예시 스크립트를 이번 대상에 맞게 고쳐 쓴다.
스크립트는 매번 새로 작성한다. 고정 스크립트를 돌리는 것이 아니라, 정찰 결과에 따라 편성과 임무를 조정한다.

## 1. 편성 원칙

- 파이프라인 구조: `전문 조사(병렬) → 영역별 교차 검증 → Bull/Bear 대심 + 완결성 감사 → 최종 판단`
- 전문 조사와 교차 검증은 pipeline으로 묶는다. 한 영역의 조사가 끝나면 다른 영역을 기다리지 않고 바로 그 영역을 검증한다.
- 종합 단계(Bull/Bear/감사/최종판단)는 모든 영역 결과가 필요하므로 배리어가 정당하다.
- 기본 규모: 전문가 7~9명 + 검증 최대 각 1명 + 종합 4명. 합계 15~20개 안팎.
  "가볍게" 요청이면 전문가 4~5명으로 줄이고, "철저히" 요청이면 검증과 전문가를 늘린다.

### 모델 라우팅

토큰 비용의 대부분은 검색을 수행하는 수집 병력에서 나온다. "수집은 내리고 판단은 유지"가 기본 전략이다.

| 단계 | model 지정 | 이유 |
|---|---|---|
| 전문 조사 | `'sonnet'` | 검색, 수집, 구조화 중심. 개수가 가장 많아 비용 대부분을 차지한다 |
| 교차 검증 | `'sonnet'` | 독립 출처 재검색 중심 |
| 완결성 감사 | `'sonnet'` | digest를 프레임워크와 대조하는 작업 |
| Bull / Bear | 지정 안 함 (세션 모델 상속) | 논증 품질이 리포트의 핵심이다 |
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
| `product` | 단지 상품성 | `complex` 모드 |
| `comps` | 비교 단지 / 후보 발굴 | `complex`, `candidate`, `compare` 모드 |
| `supply` | 공급/입주 물량 | `scenario` 모드 또는 공급 이슈 지역 |
| (동적 추가) | 재해 특화, 인구/수요, 특정 사업 전담 등 | 정찰에서 발견된 특수 이슈 |

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
    { title: '전문 조사', detail: '영역별 전문가 병렬 리서치', model: 'sonnet' },
    { title: '교차 검증', detail: '핵심 주장 반박 시도와 재확인', model: 'sonnet' },
    { title: '종합', detail: 'Bull/Bear 대심, 완결성 감사, 최종 판단' },
  ],
}

// args: { target, address, mode, asOf, skillDir, traits, purposeHint, budgetHint }
const T = args
const DIR = T.skillDir

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
    sources: { type: 'array', items: SOURCE },
  },
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
  },
}

const COMMON = [
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
  '- sources의 url에는 실제로 열어 확인한 URL만 넣어라.',
  '- 너의 최종 출력은 사람용 문장이 아니라 스키마에 맞는 구조화 데이터다.',
].filter(Boolean).join('\n')

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
  // complex/candidate/compare 모드에서 추가:
  // { key: 'comps', title: '비교 단지', mission: '조사 대상과 비교할 단지 3~4개를 스스로 선정해라. 기준은 같은 생활권 또는 인접 생활권에서 비슷한 평형대이면서 연식/세대수/역거리 조합이 의미 있는 대조를 만드는 단지다. 각 비교 단지의 최근 실거래, 평당가, 연식, 세대수, 역거리, 전세가율을 수집하고 "왜 가격 차이가 나는가"를 분석해라. 선정 이유를 반드시 밝혀라.' },
]

log('전문 조사 시작: ' + SPECIALISTS.map(s => s.title).join(', '))

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

// 종합 단계는 모든 영역 결과가 필요하므로 여기서부터 배리어가 정당하다.
const digest = JSON.stringify(domains.map(d => ({
  영역: d.title,
  요약: d.report.summary,
  발견: (d.report.findings || []).map(f => ({
    주장: f.claim, 구분: f.kind, 상태: f.status, 수치: f.figure || null, 기준일: f.as_of || null, 핵심: f.critical,
  })),
  검증결과: d.verified,
  미확인: d.report.unresolved,
})))

log('영역 조사 완료. Bull/Bear 대심과 완결성 감사를 시작한다')

const CASE_RULES = '조사 결과 digest에 있는 근거만 사용해라. 근거가 부족할 때만 최소한으로 추가 검색해라.\n' +
  '검증에서 "기각" 또는 "판단 불가"가 된 주장은 근거로 쓰지 마라.\n\n[조사 결과 digest]\n' + digest

// Bull/Bear와 최종 판단에는 model을 지정하지 않는다. 세션 모델(가장 좋은 등급)을 상속한다.
const [bull, bear, gaps] = await parallel([
  () => agent(COMMON + '\n\n[역할] 매수 옹호론자 (Bull)\n"' + T.target + '"을(를) 매수해야 하는 이유를 가장 설득력 있게 구성해라.\n' + CASE_RULES,
    { label: 'Bull', phase: '종합', schema: CASE }),
  () => agent(COMMON + '\n\n[역할] 매수 신중론자 (Bear)\n"' + T.target + '" 매수가 잘못된 선택일 수 있는 이유를 가장 설득력 있게 구성해라.\n' + CASE_RULES,
    { label: 'Bear', phase: '종합', schema: CASE }),
  () => agent(COMMON + '\n\n[역할] 완결성 감사관\n조사 결과 digest를 보고 "무엇이 빠졌는가"만 찾아라. 추가 검색은 하지 마라. 조사되지 않은 영역, 검증되지 않은 핵심 주장, 서로 어긋나는 수치를 보고해라.\n\n[조사 결과 digest]\n' + digest,
    { label: '완결성', phase: '종합', schema: GAPS, model: 'sonnet' }),
])

const judge = await agent(
  COMMON + '\n\n[역할] 수석 애널리스트\n' +
  '아래 Bull/Bear 논거와 조사 digest를 종합해 최종 판단을 내려라.\n' +
  '"내가 이 집을 내 돈으로 산다면 무엇 때문에 사고, 무엇 때문에 망설일 것인가"에 답해라.\n' +
  '판단은 "매수 고려/적극 검토/관망/비추천" 중 하나다. 투자 권유 표현은 금지다.\n' +
  '실거주 관점과 자산가치 관점이 다르면 분리해서 서술해라.\n\n' +
  '[Bull]\n' + JSON.stringify(bull) + '\n\n[Bear]\n' + JSON.stringify(bear) + '\n\n[조사 결과 digest]\n' + digest,
  { label: '최종판단', phase: '종합', schema: JUDGE }
)

return { asOf: T.asOf, target: T.target, mode: T.mode, domains, bull, bear, gaps, judge }
```

## 4. 모드별 수정 포인트

- `complex`: `product`, `comps` 전문가를 추가한다. price 임무를 "이 단지의 평형별 실거래 전수"로 좁힌다.
- `candidate`: `comps`를 "후보 발굴" 임무로 바꾼다. "조건(예산, 평형)에 맞는 후보 단지 3~6개를 발굴하고 각각의 최근 실거래와 특징을 수집해라. 후보마다 선정 이유를 밝혀라."
- `compare`: 비교 대상들이 명시돼 있으므로 `comps` 임무에 대상 목록을 박아 넣고, price/product를 비교 대상 전체로 확장한다.
- `scenario`: `supply`(입주 예정 물량, 청약홈/지자체 공급계획)와 인구/수요 전문가를 추가하고, judge 프롬프트에 "낙관/기준/비관 시나리오를 구분하되 각 시나리오의 전제(확정 사실인지 가설인지)를 명시해라"를 추가한다.

## 5. 실행 후 처리

- `gaps.missing`과 `gaps.unverified`에서 매수 판단을 좌우하는 항목만 골라 보강 에이전트를 1라운드 띄운다 (Agent 도구로 충분하다).
- `gaps.conflicts`는 리포트의 해당 섹션에서 충돌 내용과 해석을 명시한다.
- 결과가 비어 보이면 워크플로 transcript 디렉토리의 `journal.jsonl`을 읽어 각 agent의 실제 반환값을 확인한다.
- 워크플로가 중간에 죽었으면 같은 scriptPath에 `resumeFromRunId`를 붙여 재개한다. 완료된 조사는 캐시로 즉시 돌아온다.

## 6. Workflow 도구가 없는 환경의 폴백

1. 위 SPECIALISTS의 프롬프트(COMMON + 역할 + 임무)를 그대로 사용해 Agent(또는 Task) 도구로 병렬 실행한다.
   모델 라우팅도 동일하게 적용한다 (수집/검증은 model 파라미터로 sonnet, 판단부는 지정 없이 상속).
2. 각 결과에서 critical 주장을 뽑아 검증 에이전트를 병렬 실행한다.
3. Bull/Bear/완결성 에이전트를 병렬 실행하고, 최종 판단 에이전트를 실행한다.
4. 구조화 출력 스키마를 강제할 수 없으므로, 프롬프트에 "위 스키마 형태의 JSON만 반환해라"를 명시하고 반환 JSON을 직접 파싱한다.
