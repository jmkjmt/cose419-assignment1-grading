# Assignment Grading Script

이 스크립트는 학생들이 제출한 patch 파일들을 자동으로 평가하기 위한 채점 도구입니다.  
각 patch에 대해 **coverage 기반 분류**, **형식 조건**, **mutation testing**, **중복 여부**를 종합적으로 검사하여 결과를 CSV로 출력합니다.

---

## 디렉토리 구조

다음과 같은 구조를 가정합니다:

```

cose419-assignment1-grading/
├── click/                  # 기준 레포지토리 (BASE_REPO)
├── submissions/            # 학생 제출물
│   ├── sub1/
│   │   ├── covered/
│   │   │   ├── patch01.patch
|   |   |   ...
│   │   ├── uncovered/
│   │   │   ├── patch06.patch
|   |   |   ...
│   ├── sub2/
│   │   ├── covered/
│   │   ├── uncovered/
│   ...
├── grade.py
├── Dockerfile
```

---

## 사전 준비

### 1. Docker 설치
Docker가 설치되어 있고 실행 중이어야 합니다.

### 2. Docker 이미지 빌드

```bash
docker build -t click-test .
```

실행이 완료되면 다음 파일이 생성됩니다:

```
result.csv
```

---

## 출력 형식 (result.csv)

각 patch에 대해 아래 항목이 평가됩니다:

| column | 설명 |
|--------|------|
| student | 학생 ID |
| patch | patch 파일 이름 |
| classification | covered/uncovered 분류 정확성 |
| single_hunk | 단일 hunk 및 연속 라인 여부 |
| survive | 테스트 통과 여부 |
| distinct_lines | 다른 patch와 라인 중복 여부 |

표기 방식:
- `O` : 조건 만족
- `X` : 조건 불만족

---

## 채점 기준 상세

### 1. Classification
- baseline coverage 기준으로 판단
- patch가 수정한 라인 중 하나라도 실행되면 `covered`
- 학생이 제출한 label과 비교하여 일치 여부 평가

---

### 2. Single Hunk
- patch의 hunk 개수가 정확히 1개인지 확인
- 추가된 라인이 연속된 라인인지 확인

---

### 3. Survive (Mutation Testing)
- patch를 적용한 후 pytest 실행
- 테스트를 통과하면 `O` (survived mutant)

---

### 4. Distinct Lines
- 동일 학생 내 patch들 간 비교
- 수정된 라인이 겹치지 않으면 `O`
- 겹치면 해당 patch들은 `X`

---

## 내부 동작 개요

스크립트는 다음 순서로 동작합니다:

1. **Baseline Coverage 측정**
   - Docker 환경에서 pytest + coverage 실행
   - 실행된 라인 정보를 수집

2. **Patch Parsing**
   - patch 파일에서 다음 정보 추출
     - 수정된 파일 경로
     - 추가된 라인 번호
     - hunk 개수

3. **Patch 적용 및 테스트**
   - 각 patch를 임시 디렉토리에 적용
   - Docker에서 pytest 실행

4. **Distinct 분석**
   - 동일 학생 내 patch 간 라인 중복 여부 확인

5. **CSV 결과 생성**

---

## ⏱️ 제한 사항

- 각 patch는 독립적으로 평가됨 (fresh repo 사용)
- 테스트 실행 시간은 최대 20초로 제한됨
- patch 적용 실패 시 해당 patch는 자동으로 실패 처리됨
