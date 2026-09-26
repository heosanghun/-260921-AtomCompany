import json
import os
from typing import List, Dict, Any

# --- 핵심 로직 ---

def add_todo(data_file_path: str, todo_content: str) -> bool:
    """
    Todo 항목을 JSON 파일에 추가하고 저장합니다.
    데이터 파일이 없으면 새 파일을 생성합니다.
    """
    new_todo = {"content": todo_content, "done": False}
    
    # 기존 데이터 로드 또는 빈 리스트 초기화
    try:
        if os.path.exists(data_file_path):
            with open(data_file_path, 'r', encoding='utf-8') as f:
                data: List[Dict[str, Any]] = json.load(f)
        else:
            data: List[Dict[str, Any]] = []
    except json.JSONDecodeError:
        # 파일은 존재하나 JSON 형식이 아닐 경우 빈 리스트로 시작
        data: List[Dict[str, Any]] = []
    except Exception:
        # 기타 입출력 에러 시 빈 리스트로 처리하고 로직을 진행할지 결정해야 하지만,
        # 여기서는 안전하게 빈 리스트로 가정하고 진행합니다.
        data: List[Dict[str, Any]] = []

    # 중복 검사 로직은 단순화하여 항상 추가한다고 가정합니다.
    data.append(new_todo)

    # 변경된 내용을 파일에 덮어쓰기
    try:
        with open(data_file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"데이터 저장 실패: {e}")
        return False

def list_todos(data_file_path: str) -> List[Dict[str, Any]]:
    """
    저장된 모든 Todo 목록을 불러와 리스트 형태로 반환합니다.
    파일이 없으면 빈 리스트를 반환합니다.
    """
    if not os.path.exists(data_file_path):
        return []
    
    try:
        with open(data_file_path, 'r', encoding='utf-8') as f:
            data: List[Dict[str, Any]] = json.load(f)
            return data
    except json.JSONDecodeError:
        print("경고: 데이터 파일이 손상되어 빈 목록을 반환합니다.")
        return []
    except Exception as e:
        print(f"데이터 로드 중 에러 발생: {e}")
        return []

# --- CLI 시뮬레이션 함수 (실제 CLI 역할을 함) ---

def cli_add_todo(data_file_path: str, content: str) -> str:
    """CLI에서 호출될 시뮬레이션 함수: Todo 추가 및 성공 메시지 반환"""
    if add_todo(data_file_path, content):
        return f"'{content}' 작업이 성공적으로 추가되었습니다."
    return "오류: Todo 추가에 실패했습니다."

def cli_list_todos(data_file_path: str) -> str:
    """CLI에서 호출될 시뮬레이션 함수: Todo 목록을 포맷팅하여 반환"""
    todos = list_todos(data_file_path)
    if not todos:
        return "등록된 Todo 목록이 없습니다."
    
    output = ["--- Todo 목록 ---"]
    for i, todo in enumerate(todos):
        status = "[완료]" if todo.get("done") else "[진행중]"
        output.append(f"{i+1}. {status} {todo['content']}")
    
    return "\n".join(output)

# __main__ 블록은 CLI 실행을 가정하지만, 테스트를 위해 주석 처리하거나 테스트용으로 남깁니다.
if __name__ == '__main__':
    # 사용 예시: 실제 사용 시에는 데이터를 저장할 경로를 지정해야 합니다.
    # 임시 파일 경로를 직접 지정하여 테스트용으로 사용합니다.
    # test_file = "temp_data.json"
    # print("="*20)
    # print("Todo 추가 테스트:")
    # result_add = cli_add_todo(test_file, "오늘의 할 일")
    # print(result_add)
    # print("="*20)
    # print("Todo 목록 조회 테스트:")
    # result_list = cli_list_todos(test_file)
    # print(result_list)
    # print("="*20)
    pass