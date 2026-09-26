import unittest
from unittest.mock import patch
import sys
import io
from todo_cli import simulate_cli_run, TODO_LIST

# 테스트 전, 초기 상태로 리스트를 초기화합니다.
# 전역 상태를 테스트하기 위해 모든 테스트 전에 리스트를 초기화하는 것이 중요합니다.
# 이 클래스를 상속받아 테스트를 수행하여 전역 상태 초기화를 보장합니다.
class TestTodoCLI(unittest.TestCase):

    def setUp(self):
        # 테스트 시작 전 전역 상태를 초기화합니다. (가장 중요)
        global TODO_LIST
        TODO_LIST[:] = [
            {"task": "오늘 회의 자료 준비", "done": False},
            {"task": "API 문서 검토", "done": False},
            {"task": "주간 보고서 초안 작성", "done": True},
        ]
        # stdout 모킹을 설정하여 출력 메시지를 캡처합니다.
        self.held_stdout = io.StringIO()
        self.patcher = patch('sys.stdout', self.held_stdout)
        self.mock_stdout = self.patcher.start()

    def tearDown(self):
        # 테스트 종료 시 캡처된 출력을 비우고, 모킹을 해제합니다.
        self.held_stdout.seek(0)
        self.held_stdout.truncate(0)
        self.patcher.stop()
        # 전역 상태 초기화는 setUp에서 이미 처리되었으므로 별도 조치 불필요

    # ==============================================================
    # 🟢 1. 성공 케이스 테스트 (Happy Path)
    # ==============================================================

    def test_01_list_success(self):
        """리스트 명령어 실행 시 성공 여부를 검증합니다."""
        result = simulate_cli_run('list', [])
        self.assertTrue(result['success'])
        self.assertIn("성공적으로 표시했습니다", result['output'])

    def test_02_add_success(self):
        """할 일 추가 성공 시 성공 여부를 검증하고, 전역 상태 변경을 확인합니다."""
        initial_count = len(TODO_LIST)
        result = simulate_cli_run('add', ["새로운", "태스크", "설명"])
        
        self.assertTrue(result['success'])
        self.assertEqual(len(TODO_LIST), initial_count + 1)
        self.assertTrue(TODO_LIST[-1]['task'] == "새로운 태스크 설명")
        self.assertIn("할 일이 추가되었습니다", result['output'])

    def test_03_complete_success(self):
        """유효한 인덱스를 사용하여 완료 처리 성공 여부를 검증하고, 전역 상태 변경을 확인합니다."""
        # 1번 인덱스(첫 번째 할 일)를 완료 처리 시도
        result = simulate_cli_run('complete', ['1'])
        
        self.assertTrue(result['success'])
        self.assertTrue(TODO_LIST[0]['done'])
        self.assertIn("완료 처리되었습니다", result['output'])

    # ==============================================================
    # 🔴 2. 실패/예외 케이스 테스트 (Failure Path) - 핵심
    # ==============================================================

    def test_04_complete_invalid_index_for_complete(self):
        """비즈니스 로직상 유효하지 않은 인덱스(0)를 전달하여 실패하는지 검증합니다."""
        # 인덱스 0은 1부터 시작하므로 실패해야 함.
        result = simulate_cli_run('complete', ['0'])
        
        self.assertFalse(result['success']) # ⭐ 기대: 실패 상태가 False여야 함
        self.assertIn("유효하지 않은 할 일 인덱스", result['error'])
        self.assertIn("유효하지 않은 할 일 인덱스", result['output'])

    def test_05_complete_index_out_of_range(self):
        """목록 크기를 초과하는 인덱스를 전달하여 실패하는지 검증합니다."""
        # 현재 3개 항목이므로 99는 범위 초과임.
        result = simulate_cli_run('complete', ['99'])
        
        self.assertFalse(result['success']) # ⭐ 기대: 실패 상태가 False여야 함
        self.assertIn("벗어납니다", result['error'])
        self.assertIn("유효하지 않은 할 일 인덱스", result['output'])

    def test_06_add_missing_args(self):
        """add 명령어에 인자를 누락하여 실패하는지 검증합니다."""
        result = simulate_cli_run('add', [])
        
        self.assertFalse(result['success']) # ⭐ 기대: 실패 상태가 False여야 함
        self.assertIn("최소한 하나의 할 일 설명 인자를 필요로 합니다", result['error'])
        self.assertIn("추가할 내용이 비어 있습니다", result['output'])

    def test_07_complete_invalid_index_type(self):
        """인자가 정수가 아닌 문자열일 때(타입 오류) 실패하는지 검증합니다."""
        result = simulate_cli_run('complete', ['abc'])
        
        self.assertFalse(result['success']) # ⭐ 기대: 실패 상태가 False여야 함
        self.assertIsInstance(result['error'], str)
        self.assertIn("유효한 정수 인자가 아닙니다", result['error'])
        
    def test_08_complete_index_type_mismatch(self):
        """인자가 리스트 형태지만, 내부적으로 처리할 수 없는 상황을 가정 (실제로는 test_07과 유사하나, 시나리오 보강)."""
        # 이 테스트는 인자가 아닌 다른 타입이 들어왔을 때 발생할 수 있는 시나리오를 커버합니다.
        # 실제로는 int(args[0])에서 대부분 처리되지만, 명시적 실패 유도.
        # 여기서는 문법적 실패 시나리오를 재차 확인하는 목적으로 사용합니다.
        result = simulate_cli_run('complete', [''])
        
        self.assertFalse(result['success']) # ⭐ 기대: 실패 상태가 False여야 함
        self.assertIn("유효한 정수 인자가 아닙니다", result['error'])

    # ==============================================================
    # 🟡 3. 새로운/보강된 실패 테스트 케이스 (New Coverage)
    # ==============================================================

    def test_09_invalid_command(self):
        """존재하지 않는 명령어를 실행할 때 예외 처리되어 실패하는지 검증합니다."""
        # 'unknown_command'는 main() 함수에서 ValueError를 발생시킵니다.
        result = simulate_cli_run('unknown_command', [])
        
        self.assertFalse(result['success']) # ⭐ 기대: 실패 상태가 False여야 함
        self.assertIn("알 수 없는 명령어: 'unknown_command'", result['error'])
        self.assertIn("알 수 없는 명령어", result['output'])

    def test_10_missing_required_args_for_add(self):
        """add 명령어에 인자가 필요한데 인자가 빠진 경우 (기존 test_06의 보강)."""
        result = simulate_cli_run('add', [])
        
        self.assertFalse(result['success']) # ⭐ 기대: 실패 상태가 False여야 함
        self.assertIn("최소한 하나의 할 일 설명 인자를 필요로 합니다", result['error'])


if __name__ == '__main__':
    unittest.main()
