import unittest
import os
import json
from todo_cli import add_todo, list_todos, cli_add_todo, cli_list_todos

class TestTodoCLI(unittest.TestCase):
    
    def setUp(self):
        """각 테스트 메소드가 실행되기 전에 실행되는 셋업 메서드"""
        # 테스트 격리를 위해 임시 파일 경로를 설정합니다.
        self.temp_file_path = "temp_test_data.json"
        # 파일 존재 여부와 상관없이 테스트 시작 시 임시 파일을 '비우거나' 초기 상태로 설정하는 것이 이상적이나,
        # 여기서는 add_todo/list_todos 내부의 파일 로딩 로직을 신뢰하며, 테스트 시작 전에 깨끗한 상태를 가정합니다.
        # 강제로 파일 초기화 대신, 테스트별로 독립적인 환경을 만들기 위해 setUp에서는 아무것도 하지 않습니다.
        # 각 테스트 메소드 내에서 독립적인 동작을 보장해야 합니다.
        pass

    def tearDown(self):
        """각 테스트 메소드가 끝난 후에 실행되는 정리(Cleanup) 메서드"""
        # 테스트 종료 시 생성된 임시 파일을 반드시 삭제합니다.
        if os.path.exists(self.temp_file_path):
            os.remove(self.temp_file_path)
            print(f"\n[INFO] Cleanup: {self.temp_file_path} 파일을 성공적으로 삭제했습니다.")

    def test_01_add_single_todo(self):
        """단일 Todo 항목을 추가하고, 목록 조회로 정상적으로 보이는지 검증합니다."""
        # 1. 초기 상태에서 테스트 시작 (파일이 없거나 비어있다고 가정)
        # 강제 초기화 대신, add_todo가 파일 생성/업데이트를 처리하도록 맡깁니다.
        self.assertTrue(add_todo(self.temp_file_path, "새로운 첫 번째 할 일"))
        
        # 2. 추가된 항목을 목록으로 조회하여 확인
        todos = list_todos(self.temp_file_path)
        self.assertEqual(len(todos), 1)
        self.assertEqual(todos[0]['content'], "새로운 첫 번째 할 일")

    def test_02_add_multiple_todos(self):
        """여러 개의 Todo 항목을 순차적으로 추가하고, 전체 목록을 확인합니다."""
        # 1. 첫 번째 항목 추가 (파일 생성 유도)
        add_todo(self.temp_file_path, "점심 식사 계획")
        
        # 2. 두 번째 항목 추가 (기존 파일에 덮어쓰기/추가)
        add_todo(self.temp_file_path, "보고서 초안 작성")
        
        # 3. 총 목록을 조회하여 개수와 내용을 확인
        todos = list_todos(self.temp_file_path)
        self.assertEqual(len(todos), 2)
        
        # 순서 검증 (FIFO 가정)
        self.assertEqual(todos[0]['content'], "점심 식사 계획")
        self.assertEqual(todos[1]['content'], "보고서 초안 작성")
        
    def test_03_list_todos_when_empty(self):
        """데이터 파일이 존재하지 않거나 비어있을 때 목록 조회 기능이 빈 리스트를 반환하는지 검증합니다."""
        # 테스트 시작 전, 임시 파일을 강제로 삭제하여 비어있음 상태를 유도
        if os.path.exists(self.temp_file_path):
            os.remove(self.temp_file_path)
            
        todos = list_todos(self.temp_file_path)
        self.assertEqual(len(todos), 0)

    def test_04_cli_simulation(self):
        """CLI 함수 호출 시뮬레이션을 통해 전체 워크플로우를 검증합니다."""
        # 1. 첫 번째 항목 추가 시뮬레이션
        result_add = cli_add_todo(self.temp_file_path, "최종 검토")
        self.assertIn("성공적으로 추가되었습니다", result_add)
        
        # 2. 항목 추가 후 목록 조회 시뮬레이션
        result_list = cli_list_todos(self.temp_file_path)
        self.assertIn("최종 검토", result_list)

if __name__ == '__main__':
    # 직접 실행 시, 모든 테스트 케이스가 실행됩니다.
    unittest.main(argv=['first-arg-is-ignored'], exit=False)