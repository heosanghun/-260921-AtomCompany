import json
import os

TODO_FILE = "todo_data.json"

def _load_todos():
    """Todo 파일을 로드하거나, 파일이 없으면 빈 리스트를 반환합니다."""
    if not os.path.exists(TODO_FILE):
        return []
    try:
        with open(TODO_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        # 파일이 비어있거나 형식이 잘못된 경우 빈 리스트로 시작
        return []

def _save_todos(todos):
    """Todo 리스트를 파일에 저장합니다."""
    with open(TODO_FILE, 'w') as f:
        json.dump(todos, f, indent=4)

def add_todo(task_description: str):
    """새로운 할 일을 추가합니다."""
    todos = _load_todos()
    todos.append({"task": task_description, "done": False})
    _save_todos(todos)
    print(f"✅ 할 일 '{task_description}'이(가) 추가되었습니다.")

def list_todos():
    """현재 할 일 목록을 조회합니다."""
    todos = _load_todos()
    if not todos:
        print("📝 등록된 할 일이 없습니다.")
        return

    print("\n==== 할 일 목록 ====")
    for index, todo in enumerate(todos):
        status = "✅" if todo["done"] else "⏳"
        print(f"{index + 1}. [{status}] {todo['task']}")
    print("====================")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python todo_cli.py <command> [arguments]")
        print("Commands: add <task description>, list")
        sys.exit(1)

    command = sys.argv[1]

    if command == "add":
        if len(sys.argv) < 3:
            print("Usage: todo_cli.py add <task description>")
            sys.exit(1)
        description = " ".join(sys.argv[2:])
        add_todo(description)
    elif command == "list":
        list_todos()
    else:
        print(f"알 수 없는 명령어: {command}")
        sys.exit(1)