import unittest
import os
import json
from todo_cli import add_todo, view_todos, load_todos, save_todos, clear_todo_file

class TestTodoCLI(unittest.TestCase):
    
    TEST_FILE = "todo_list.json"

    @classmethod
    def setUpClass(cls):
        # 테스트 실행 전 임시 파일 정리
        clear_todo_file()

    @classmethod
    def tearDownClass(cls):
        # 테스트 실행 후 임시 파일 정리
        clear_todo_file()

    def setUp(self):
        # 각 테스트 메소드 실행 전에 테스트 환경 초기화
        clear_todo_file()

    def test_initial_state(self):
        """초기 상태에서 Todo 목록이 비어있는지 확인"""
        todos = load_todos()
        self.assertEqual(todos, [])

    def test_add_single_todo(self):
        """하나의 Todo 항목을 성공적으로 추가하고 저장되는지 확인"""
        todo_desc = "장보기 목록 작성"
        new_todo = add_todo(todo_desc)
        
        todos = load_todos()
        self.assertEqual(len(todos), 1)
        self.assertEqual(todos[0]['task'], todo_desc)
        self.assertFalse(todos[0]['done'])
        self.assertEqual(todos[0]['id'], 1)

    def test_add_multiple_todos(self):
        """여러 개의 Todo 항목을 순차적으로 추가하고 ID가 증가하는지 확인"""
        add_todo("첫 번째 할 일")
        add_todo("두 번째 할 일")
        
        todos = load_todos()
        self.assertEqual(len(todos), 2)
        self.assertEqual(todos[0]['id'], 1)
        self.assertEqual(todos[1]['id'], 2)

    def test_view_todos_empty(self):
        """Todo가 없을 때 view_todos가 올바른 메시지를 반환하는지 확인"""
        self.assertEqual(view_todos(), "등록된 할 일 목록이 없습니다.")

    def test_view_todos_single_item(self):
        """하나의 Todo 항목이 있을 때 view_todos가 올바르게 포맷팅되는지 확인"""
        add_todo("개별 테스트 항목")
        expected_output = "--- 할 일 목록 ---\n1. [진행] 개별 테스트 항목"
        self.assertEqual(view_todos(), expected_output)
        
    def test_view_todos_multiple_items_with_status(self):
        """여러 항목과 완료 상태가 섞여 있을 때 view_todos가 정확하게 포맷팅되는지 확인"""
        # 1. 완료된 항목 추가 (임시로 'done: true'로 오버라이딩하여 테스트)
        initial_todos = load_todos()
        initial_todos.append({"id": 1, "task": "완료된 작업", "done": True})
        save_todos(initial_todos)
        
        # 2. 진행 중인 항목 추가 (새 ID가 붙을 수 있으므로, 로직을 우회하여 직접 덮어씀)
        todos = load_todos()
        todos.append({"id": 2, "task": "진행 중인 작업", "done": False})
        save_todos(todos)
        
        # 테스트를 위해 '진행 중' 상태로 리셋하고 덮어쓰는 것이 더 안정적
        todos_test = [
            {"id": 1, "task": "완료된 작업", "done": True},
            {"id": 2, "task": "진행 중인 작업", "done": False}
        ]
        save_todos(todos_test)
        
        expected_output = (
            "--- 할 일 목록 ---\n"
            "1. [완료] 완료된 작업\n"
            "2. [진행] 진행 중인 작업"
        )
        self.assertEqual(view_todos(), expected_output)

if __name__ == '__main__':
    unittest.main()