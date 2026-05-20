"""
온톨로지 생성 서비스
인터페이스1: 텍스트 내용을 분석하여 사회 시뮬레이션에 적합한 엔티티 및 관계 유형 정의 생성
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional
from ..utils.llm_client import LLMClient
from ..utils.locale import get_language_instruction

logger = logging.getLogger(__name__)


def _to_pascal_case(name: str) -> str:
    """임의 형식의 이름을 PascalCase로 변환 (예: 'works_for' -> 'WorksFor', 'person' -> 'Person')"""
    # 비알파벳/숫자 문자로 분할
    parts = re.split(r'[^a-zA-Z0-9]+', name)
    # camelCase 경계로 추가 분할 (예: 'camelCase' -> ['camel', 'Case'])
    words = []
    for part in parts:
        words.extend(re.sub(r'([a-z])([A-Z])', r'\1_\2', part).split('_'))
    # 각 단어 첫 글자 대문자화, 빈 문자열 필터링
    result = ''.join(word.capitalize() for word in words if word)
    return result if result else 'Unknown'


# 온톨로지 생성 시스템 프롬프트
ONTOLOGY_SYSTEM_PROMPT = """당신은 전문 지식 그래프 온톨로지 설계 전문가입니다. 주어진 텍스트 내용과 시뮬레이션 요구사항을 분석하여 **소셜 미디어 여론 시뮬레이션**에 적합한 엔티티 유형과 관계 유형을 설계하는 것이 당신의 임무입니다.

**중요: 반드시 유효한 JSON 형식 데이터만 출력해야 하며, 다른 내용은 출력하지 마세요.**

## 핵심 작업 배경

우리는 **소셜 미디어 여론 시뮬레이션 시스템**을 구축하고 있습니다. 이 시스템에서:
- 각 엔티티는 소셜 미디어에서 발언하고, 상호작용하고, 정보를 전파할 수 있는 "계정" 또는 "주체"입니다
- 엔티티 간에 상호 영향, 리트윗, 댓글, 응답이 이루어집니다
- 여론 사건에서 각 측의 반응과 정보 전파 경로를 시뮬레이션해야 합니다

따라서, **엔티티는 현실에서 실제로 존재하며, 소셜 미디어에서 발언하고 상호작용할 수 있는 주체여야 합니다**:

**가능한 것**:
- 구체적인 개인 (공인, 당사자, 오피니언 리더, 전문가 학자, 일반인)
- 회사, 기업 (공식 계정 포함)
- 조직 기관 (대학, 협회, NGO, 노조 등)
- 정부 부서, 규제 기관
- 미디어 기관 (신문, TV, 1인 미디어, 웹사이트)
- 소셜 미디어 플랫폼 자체
- 특정 집단 대표 (동문회, 팬클럽, 권익 옹호 단체 등)

**불가능한 것**:
- 추상적 개념 ("여론", "감정", "트렌드" 등)
- 주제/토픽 ("학문적 성실성", "교육 개혁" 등)
- 관점/태도 ("지지측", "반대측" 등)

## 출력 형식

다음 구조를 포함하는 JSON 형식으로 출력하세요:

```json
{
    "entity_types": [
        {
            "name": "엔티티 유형 이름 (영문, PascalCase)",
            "description": "간략한 설명 (영문, 100자 이내)",
            "attributes": [
                {
                    "name": "속성명 (영문, snake_case)",
                    "type": "text",
                    "description": "속성 설명"
                }
            ],
            "examples": ["예시 엔티티1", "예시 엔티티2"]
        }
    ],
    "edge_types": [
        {
            "name": "관계 유형 이름 (영문, UPPER_SNAKE_CASE)",
            "description": "간략한 설명 (영문, 100자 이내)",
            "source_targets": [
                {"source": "소스 엔티티 유형", "target": "대상 엔티티 유형"}
            ],
            "attributes": []
        }
    ],
    "analysis_summary": "텍스트 내용에 대한 간략한 분석 설명"
}
```

## 설계 가이드 (매우 중요!)

### 1. 엔티티 유형 설계 - 반드시 엄격히 준수

**수량 요구: 정확히 10개의 엔티티 유형 필수**

**계층 구조 요구 (구체적 유형과 폴백 유형을 반드시 함께 포함)**:

10개의 엔티티 유형에는 다음 계층이 포함되어야 합니다:

A. **폴백 유형 (필수 포함, 목록 마지막 2개에 배치)**:
   - `Person`: 모든 자연인 개인의 폴백 유형. 다른 더 구체적인 인물 유형에 속하지 않을 때 이 유형으로 분류.
   - `Organization`: 모든 조직 기관의 폴백 유형. 다른 더 구체적인 조직 유형에 속하지 않을 때 이 유형으로 분류.

B. **구체적 유형 (8개, 텍스트 내용에 따라 설계)**:
   - 텍스트에 나타나는 주요 역할에 대해 더 구체적인 유형 설계
   - 예: 텍스트가 학술 사건과 관련된 경우 `Student`, `Professor`, `University` 가능
   - 예: 텍스트가 비즈니스 사건과 관련된 경우 `Company`, `CEO`, `Employee` 가능

**폴백 유형이 필요한 이유**:
- 텍스트에는 "초중등 교사", "행인", "어떤 네티즌" 등 다양한 인물이 등장
- 전용 유형이 없으면 `Person`으로 분류해야 함
- 마찬가지로 소규모 조직, 임시 단체 등은 `Organization`으로 분류

**구체적 유형 설계 원칙**:
- 텍스트에서 고빈도로 등장하거나 핵심적인 역할 유형 식별
- 각 구체적 유형은 명확한 경계가 있어야 하며 중복 방지
- description은 이 유형과 폴백 유형의 차이를 명확히 설명해야 함

### 2. 관계 유형 설계

- 수량: 6-10개
- 관계는 소셜 미디어 상호작용에서의 실제 연결을 반영해야 함
- 관계의 source_targets가 정의한 엔티티 유형을 포함하도록 보장

### 3. 속성 설계

- 각 엔티티 유형당 1-3개의 핵심 속성
- **주의**: 속성명으로 `name`, `uuid`, `group_id`, `created_at`, `summary` 사용 불가 (시스템 예약어)
- 권장: `full_name`, `title`, `role`, `position`, `location`, `description` 등

## 엔티티 유형 참조

**개인 유형 (구체적)**:
- Student: 학생
- Professor: 교수/학자
- Journalist: 기자
- Celebrity: 연예인/인플루언서
- Executive: 임원
- Official: 정부 관료
- Lawyer: 변호사
- Doctor: 의사

**개인 유형 (폴백)**:
- Person: 모든 자연인 (위의 구체적 유형에 속하지 않을 때 사용)

**조직 유형 (구체적)**:
- University: 대학교
- Company: 회사/기업
- GovernmentAgency: 정부 기관
- MediaOutlet: 미디어 기관
- Hospital: 병원
- School: 초중등학교
- NGO: 비정부 조직

**조직 유형 (폴백)**:
- Organization: 모든 조직 기관 (위의 구체적 유형에 속하지 않을 때 사용)

## 관계 유형 참조

- WORKS_FOR: 근무
- STUDIES_AT: 재학
- AFFILIATED_WITH: 소속
- REPRESENTS: 대표
- REGULATES: 규제
- REPORTS_ON: 보도
- COMMENTS_ON: 댓글
- RESPONDS_TO: 응답
- SUPPORTS: 지지
- OPPOSES: 반대
- COLLABORATES_WITH: 협력
- COMPETES_WITH: 경쟁
"""


class OntologyGenerator:
    """
    온톨로지 생성기
    텍스트 내용을 분석하여 엔티티 및 관계 유형 정의 생성
    """
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()
    
    def generate(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        온톨로지 정의 생성

        Args:
            document_texts: 문서 텍스트 목록
            simulation_requirement: 시뮬레이션 요구사항 설명
            additional_context: 추가 컨텍스트

        Returns:
            온톨로지 정의 (entity_types, edge_types 등)
        """
        # 사용자 메시지 구성
        user_message = self._build_user_message(
            document_texts, 
            simulation_requirement,
            additional_context
        )
        
        lang_instruction = get_language_instruction()
        system_prompt = f"{ONTOLOGY_SYSTEM_PROMPT}\n\n{lang_instruction}\nIMPORTANT: Entity type names MUST be in English PascalCase (e.g., 'PersonEntity', 'MediaOrganization'). Relationship type names MUST be in English UPPER_SNAKE_CASE (e.g., 'WORKS_FOR'). Attribute names MUST be in English snake_case. Only description fields and analysis_summary should use the specified language above."
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        # LLM 호출
        result = self.llm_client.chat_json(
            messages=messages,
            temperature=0.3,
            max_tokens=4096
        )
        
        # 검증 및 후처리
        result = self._validate_and_process(result)
        
        return result
    
    # LLM에 전달할 텍스트 최대 길이 (5만자)
    MAX_TEXT_LENGTH_FOR_LLM = 50000
    
    def _build_user_message(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str]
    ) -> str:
        """사용자 메시지 구성"""

        # 텍스트 병합
        combined_text = "\n\n---\n\n".join(document_texts)
        original_length = len(combined_text)

        # 텍스트가 5만자를 초과하면 절단 (LLM에 전달되는 내용에만 영향, 그래프 구축에는 영향 없음)
        if len(combined_text) > self.MAX_TEXT_LENGTH_FOR_LLM:
            combined_text = combined_text[:self.MAX_TEXT_LENGTH_FOR_LLM]
            combined_text += f"\n\n...(원문 총 {original_length}자, 온톨로지 분석을 위해 앞 {self.MAX_TEXT_LENGTH_FOR_LLM}자 추출)..."
        
        message = f"""## 시뮬레이션 요구사항

{simulation_requirement}

## 문서 내용

{combined_text}
"""

        if additional_context:
            message += f"""
## 추가 설명

{additional_context}
"""

        message += """
위 내용을 바탕으로 소셜 여론 시뮬레이션에 적합한 엔티티 유형과 관계 유형을 설계하세요.

**반드시 준수해야 할 규칙**:
1. 정확히 10개의 엔티티 유형을 출력해야 함
2. 마지막 2개는 반드시 폴백 유형: Person (개인 폴백)과 Organization (조직 폴백)
3. 앞의 8개는 텍스트 내용에 따라 설계된 구체적 유형
4. 모든 엔티티 유형은 현실에서 발언할 수 있는 주체여야 하며, 추상적 개념 불가
5. 속성명으로 name, uuid, group_id 등 예약어 사용 불가, full_name, org_name 등으로 대체
"""
        
        return message
    
    def _validate_and_process(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """검증 및 후처리 결과"""

        # 필수 필드 존재 확인
        if "entity_types" not in result:
            result["entity_types"] = []
        if "edge_types" not in result:
            result["edge_types"] = []
        if "analysis_summary" not in result:
            result["analysis_summary"] = ""

        # 엔티티 유형 검증
        # 원본 이름에서 PascalCase로의 매핑 기록, 추후 edge의 source_targets 참조 수정에 사용
        entity_name_map = {}
        for entity in result["entity_types"]:
            # 엔티티 이름을 PascalCase로 강제 변환 (Zep API 요구사항)
            if "name" in entity:
                original_name = entity["name"]
                entity["name"] = _to_pascal_case(original_name)
                if entity["name"] != original_name:
                    logger.warning(f"Entity type name '{original_name}' auto-converted to '{entity['name']}'")
                entity_name_map[original_name] = entity["name"]
            if "attributes" not in entity:
                entity["attributes"] = []
            if "examples" not in entity:
                entity["examples"] = []
            # description이 100자를 초과하지 않도록 보장
            if len(entity.get("description", "")) > 100:
                entity["description"] = entity["description"][:97] + "..."
        
        # 관계 유형 검증
        for edge in result["edge_types"]:
            # 엣지 이름을 SCREAMING_SNAKE_CASE로 강제 변환 (Zep API 요구사항)
            if "name" in edge:
                original_name = edge["name"]
                edge["name"] = original_name.upper()
                if edge["name"] != original_name:
                    logger.warning(f"Edge type name '{original_name}' auto-converted to '{edge['name']}'")
            # source_targets의 엔티티 이름 참조 수정, 변환된 PascalCase와 일치하도록 유지
            for st in edge.get("source_targets", []):
                if st.get("source") in entity_name_map:
                    st["source"] = entity_name_map[st["source"]]
                if st.get("target") in entity_name_map:
                    st["target"] = entity_name_map[st["target"]]
            if "source_targets" not in edge:
                edge["source_targets"] = []
            if "attributes" not in edge:
                edge["attributes"] = []
            if len(edge.get("description", "")) > 100:
                edge["description"] = edge["description"][:97] + "..."
        
        # Zep API 제한: 최대 10개 사용자 정의 엔티티 유형, 최대 10개 사용자 정의 엣지 유형
        MAX_ENTITY_TYPES = 10
        MAX_EDGE_TYPES = 10

        # 중복 제거: name 기준으로 중복 제거, 첫 번째 출현 유지
        seen_names = set()
        deduped = []
        for entity in result["entity_types"]:
            name = entity.get("name", "")
            if name and name not in seen_names:
                seen_names.add(name)
                deduped.append(entity)
            elif name in seen_names:
                logger.warning(f"Duplicate entity type '{name}' removed during validation")
        result["entity_types"] = deduped

        # 폴백 유형 정의
        person_fallback = {
            "name": "Person",
            "description": "Any individual person not fitting other specific person types.",
            "attributes": [
                {"name": "full_name", "type": "text", "description": "Full name of the person"},
                {"name": "role", "type": "text", "description": "Role or occupation"}
            ],
            "examples": ["ordinary citizen", "anonymous netizen"]
        }
        
        organization_fallback = {
            "name": "Organization",
            "description": "Any organization not fitting other specific organization types.",
            "attributes": [
                {"name": "org_name", "type": "text", "description": "Name of the organization"},
                {"name": "org_type", "type": "text", "description": "Type of organization"}
            ],
            "examples": ["small business", "community group"]
        }
        
        # 폴백 유형 존재 여부 확인
        entity_names = {e["name"] for e in result["entity_types"]}
        has_person = "Person" in entity_names
        has_organization = "Organization" in entity_names

        # 추가해야 할 폴백 유형
        fallbacks_to_add = []
        if not has_person:
            fallbacks_to_add.append(person_fallback)
        if not has_organization:
            fallbacks_to_add.append(organization_fallback)
        
        if fallbacks_to_add:
            current_count = len(result["entity_types"])
            needed_slots = len(fallbacks_to_add)

            # 추가 후 10개를 초과하면 일부 기존 유형 제거 필요
            if current_count + needed_slots > MAX_ENTITY_TYPES:
                # 제거해야 할 개수 계산
                to_remove = current_count + needed_slots - MAX_ENTITY_TYPES
                # 뒤에서부터 제거 (앞의 더 중요한 구체적 유형 유지)
                result["entity_types"] = result["entity_types"][:-to_remove]

            # 폴백 유형 추가
            result["entity_types"].extend(fallbacks_to_add)

        # 최종적으로 제한 초과하지 않도록 보장 (방어적 프로그래밍)
        if len(result["entity_types"]) > MAX_ENTITY_TYPES:
            result["entity_types"] = result["entity_types"][:MAX_ENTITY_TYPES]
        
        if len(result["edge_types"]) > MAX_EDGE_TYPES:
            result["edge_types"] = result["edge_types"][:MAX_EDGE_TYPES]
        
        return result
    
    def generate_python_code(self, ontology: Dict[str, Any]) -> str:
        """
        온톨로지 정의를 Python 코드로 변환 (ontology.py와 유사)

        Args:
            ontology: 온톨로지 정의

        Returns:
            Python 코드 문자열
        """
        code_lines = [
            '"""',
            '사용자 정의 엔티티 유형 정의',
            'MiroFish에서 자동 생성, 사회 여론 시뮬레이션용',
            '"""',
            '',
            'from pydantic import Field',
            'from zep_cloud.external_clients.ontology import EntityModel, EntityText, EdgeModel',
            '',
            '',
            '# ============== 엔티티 유형 정의 ==============',
            '',
        ]

        # 엔티티 유형 생성
        for entity in ontology.get("entity_types", []):
            name = entity["name"]
            desc = entity.get("description", f"A {name} entity.")
            
            code_lines.append(f'class {name}(EntityModel):')
            code_lines.append(f'    """{desc}"""')
            
            attrs = entity.get("attributes", [])
            if attrs:
                for attr in attrs:
                    attr_name = attr["name"]
                    attr_desc = attr.get("description", attr_name)
                    code_lines.append(f'    {attr_name}: EntityText = Field(')
                    code_lines.append(f'        description="{attr_desc}",')
                    code_lines.append(f'        default=None')
                    code_lines.append(f'    )')
            else:
                code_lines.append('    pass')
            
            code_lines.append('')
            code_lines.append('')

        code_lines.append('# ============== 관계 유형 정의 ==============')
        code_lines.append('')

        # 관계 유형 생성
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            # PascalCase 클래스명으로 변환
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            desc = edge.get("description", f"A {name} relationship.")
            
            code_lines.append(f'class {class_name}(EdgeModel):')
            code_lines.append(f'    """{desc}"""')
            
            attrs = edge.get("attributes", [])
            if attrs:
                for attr in attrs:
                    attr_name = attr["name"]
                    attr_desc = attr.get("description", attr_name)
                    code_lines.append(f'    {attr_name}: EntityText = Field(')
                    code_lines.append(f'        description="{attr_desc}",')
                    code_lines.append(f'        default=None')
                    code_lines.append(f'    )')
            else:
                code_lines.append('    pass')
            
            code_lines.append('')
            code_lines.append('')

        # 유형 딕셔너리 생성
        code_lines.append('# ============== 유형 설정 ==============')
        code_lines.append('')
        code_lines.append('ENTITY_TYPES = {')
        for entity in ontology.get("entity_types", []):
            name = entity["name"]
            code_lines.append(f'    "{name}": {name},')
        code_lines.append('}')
        code_lines.append('')
        code_lines.append('EDGE_TYPES = {')
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            code_lines.append(f'    "{name}": {class_name},')
        code_lines.append('}')
        code_lines.append('')

        # 엣지의 source_targets 매핑 생성
        code_lines.append('EDGE_SOURCE_TARGETS = {')
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            source_targets = edge.get("source_targets", [])
            if source_targets:
                st_list = ', '.join([
                    f'{{"source": "{st.get("source", "Entity")}", "target": "{st.get("target", "Entity")}"}}'
                    for st in source_targets
                ])
                code_lines.append(f'    "{name}": [{st_list}],')
        code_lines.append('}')
        
        return '\n'.join(code_lines)

