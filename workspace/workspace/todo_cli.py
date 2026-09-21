import json
import os

TODO_FILE = "todo_list.json"

def load_todos():
    """todo_list.json에서 Todo 목록을 불러옵니다. 파일이 없으면 빈 리스트를 반환합니다."""
    if not os.path.exists(TODO_FILE):
        return []
    try:
        with open(TODO_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        # 파일이 비어있거나 형식이 잘못되었을 경우 초기화
        return []

def save_todos(todos):
    """Todo 목록을 todo_list.json 파일에 저장합니다."""
    with open(TODO_FILE, 'w', encoding='utf-8') as f:
        json.dump(todos, f, indent=4, ensure_ascii=False)

def add_todo(task_description):
    """새로운 Todo 항목을 추가합니다. (테스트 용이성을 위해 상태값만 반환)"""
    todos = load_todos()
    # ID는 현재 목록의 크기 + 1로 가정하고 부여 (간단 버전)
    new_id = len(todos) + 1 if todos else 1
    new_todo = {
        "id": new_id,
        "task": task_description,
        "done": False
    }
    todos.append(new_todo)
    save_todos(todos)
    return new_todo

def view_todos():
    """현재 Todo 목록을 조회합니다. (테스트 용이성을 위해 문자열 반환)"""
    todos = load_todos()
    if not todos:
        return "등록된 할 일 목록이 없습니다."
    
    output = ["--- 할 일 목록 ---"]
    for todo in todos:
        status = "[완료]" if todo["done"] else "[진행]"
        output.append(f"{todo['id']}. {status} {todo['task']}")
    
    return "\n".join(output)

# CLI 인터페이스를 위한 main 함수 (테스트 시에는 사용되지 않거나, 테스트 코드를 간결하게 하기 위해 비워둡니다)
def main_cli():
    pass

# 임시로 테스트를 위해 파일 상태를 초기화하는 함수 (테스트 실행 전후에 사용)
def clear_todo_file():
    if os.path.exists(TODO_FILE):
        os.remove(TODO_FILE)
