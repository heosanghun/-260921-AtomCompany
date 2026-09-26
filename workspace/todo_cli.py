import argparse
import sys
from typing import Dict, Any

# --- Data Model ---
TODO_LIST = [
    {"task": "오늘 회의 자료 준비", "done": False},
    {"task": "API 문서 검토", "done": False},
    {"task": "주간 보고서 초안 작성", "done": True},
]

def display_todos(todos: list):
    """전체 할 일 목록을 보기 좋게 출력합니다."""
    print("=" * 30)
    print("📝 TODO 리스트")
    print("=" * 30)
    if not todos:
        print("처리할 할 일이 없습니다.")
        return

    for i, task_data in enumerate(todos):
        status = "[DONE]" if task_data["done"] else "[TODO]"
        print(f"{i+1}. {status} {task_data['task']}")

def add_todo(task_desc: str) -> bool:
    """새로운 할 일을 추가합니다."""
    TODO_LIST.append({"task": task_desc, "done": False})
    print(f"✅ '{task_desc}' 할 일이 추가되었습니다.")
    return True

def list_todos(args: list) -> bool:
    """모든 할 일 목록을 출력합니다."""
    display_todos(TODO_LIST)
    return True

def complete_todo(task_index: int) -> bool:
    """특정 인덱스의 할 일을 완료 처리합니다."""
    # 인덱스 검증: 1부터 시작하는지 확인
    if not (1 <= task_index <= len(TODO_LIST)):
        print(f"❌ 오류: 유효하지 않은 할 일 인덱스입니다. 1부터 {len(TODO_LIST)} 사이의 숫자를 사용하세요.")
        return False

    # 0-based 인덱스로 변환
    index = task_index - 1
    if TODO_LIST[index]["done"]:
        print(f"⚠️ 이미 완료된 항목입니다: {TODO_LIST[index]['task']}")
        return True # 완료 시도이지만, 이미 완료 상태로 간주하여 성공으로 처리할 수도 있지만, 여기서는 사용자에게 알림 후 성공으로 처리
    
    TODO_LIST[index]["done"] = True
    print(f"🎉 '{TODO_LIST[index]['task']}' 항목이 완료 처리되었습니다.")
    return True

def simulate_cli_run(command: str, args: list) -> Dict[str, Any]:
    """
    명령어와 인자를 받아 CLI를 시뮬레이션하고, 실행 결과를 딕셔너리로 반환합니다.
    이 함수는 상태 전파의 신뢰성을 최우선으로 설계되었습니다.
    """
    result: Dict[str, Any] = {"success": False, "output": "", "error": None}
    
    try:
        # 1. 명령어 유효성 검사
        if command not in ["add", "list", "complete"]:
            raise ValueError(f"알 수 없는 명령어: '{command}'. 'add', 'list', 'complete' 중 하나를 사용하세요.")

        if command == "add":
            if not args or len(args) < 1:
                raise ValueError("add 명령어는 최소한 하나의 할 일 설명 인자를 필요로 합니다.")
            
            # add 명령어는 첫 번째 인자를 사용하고, 나머지 인자는 공백으로 처리 (간단화)
            task_desc = " ".join(args)
            if not task_desc:
                 raise ValueError("추가할 내용이 비어 있습니다.")
            
            success = add_todo(task_desc)
            if success:
                result['output'] = f"작업 성공적으로 완료. 할 일 추가됨."
                result['success'] = True
            else:
                # 내부 로직 오류로 실패하는 경우 (이 시나리오에서는 잘 일어나지 않음)
                result['output'] = "할 일 추가에 실패했습니다."
                result['success'] = False

        elif command == "list":
            # list 명령어는 인자를 받지 않거나, 받더라도 무시함
            success = list_todos(args)
            if success:
                result['output'] = "할 일 목록을 성공적으로 표시했습니다."
                result['success'] = True

        elif command == "complete":
            if len(args) != 1:
                raise ValueError("complete 명령어는 정확히 하나의 인자(task_index)를 필요로 합니다.")
            
            try:
                # 인자 타입 변환 및 검증 (실패 시 예외 발생 유도)
                task_index = int(args[0])
                
                # 비즈니스 로직 검증: Task Index 유효성 검사
                if not (1 <= task_index <= len(TODO_LIST)):
                     raise IndexError(f"인덱스 {task_index}는 현재 목록 크기를 벗어납니다.")
                
                # 실제 완료 로직 실행
                success = complete_todo(task_index)
                if success:
                    result['output'] = f"작업 성공적으로 완료. {task_index}번째 항목 완료 처리됨."
                    result['success'] = True
                else:
                    # 비즈니스 로직 상 실패 (예: 이미 완료)
                    result['output'] = "할 일 완료 처리에 실패했습니다."
                    result['success'] = False

            except ValueError:
                # int 변환 실패 또는 길이 검사 실패 (타입/개수 오류)
                raise TypeError(f"'{args[0]}'은(는) 유효한 정수 인자가 아닙니다.")
            except IndexError as e:
                # 비즈니스 로직상 범위를 벗어나는 경우
                raise e
    
    except (ValueError, TypeError, IndexError) as e:
        # ⭐ 핵심 수정 지점: 모든 예외 발생 시, 성공 상태를 명시적으로 False로 설정하고 에러 정보를 기록합니다.
        result['error'] = str(e)
        result['output'] = f"명령어/인자 처리 중 오류 발생: {e}"
        result['success'] = False # <-- ★★★★ 가장 중요한 수정 사항 ★★★★
    
    except Exception as e:
        # 예상치 못한 모든 기타 예외 처리
        result['error'] = f"예상치 못한 시스템 오류 발생: {type(e).__name__}"
        result['output'] = f"치명적인 시스템 오류가 발생하여 작업을 중단합니다."
        result['success'] = False # <-- ★★★★ 안전장치 (Safety Net) ★★★★

    return result

def main():
    """CLI 인터페이스의 주 진입점 (테스트 환경에서는 사용되지 않음)."""
    parser = argparse.ArgumentParser(description="간단한 할 일 관리 CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # add parser
    parser_add = subparsers.add_parser('add', help='새로운 할 일을 추가합니다.')
    parser_add.add_argument('task_description', type=str, nargs='+', help='추가할 할 일 설명 (공백으로 구분)')

    # list parser
    subparsers.add_parser('list', help='모든 할 일 목록을 조회합니다.')

    # complete parser
    parser_complete = subparsers.add_parser('complete', help='완료할 할 일의 인덱스를 지정합니다.')
    # ★★★ 문법 오류 수정: type=int, 형태로 수정
    parser_complete.add_argument('task_index', type=int, help='완료할 할 일의 인덱스 (1부터 시작)')

    args = parser.parse_args()
    
    # 테스트용 헬퍼 함수 호출 유도 로직 (실제 CLI 작동 시)
    if args.command == 'add':
        simulate_cli_run('add', args.task_description)
    elif args.command == 'list':
        simulate_cli_run('list', [])
    elif args.command == 'complete':
        simulate_cli_run('complete', [str(args.task_index)])

if __name__ == "__main__":
    # 이 부분은 실제 실행 테스트를 위해 유지합니다.
    main()
