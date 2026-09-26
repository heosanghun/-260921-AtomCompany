import unittest
from datetime import datetime
from workspace.models.todo import TodoManager, Todo

class TestTodoManager(unittest.TestCase):
    def setUp(self):
        # 매 테스트마다 깨끗한 환경에서 시작하기 위해 새 매니저 인스턴스 사용
        self.manager = TodoManager()
        # 테스트를 위해 강제로 몇 가지 할 일을 추가 (실제로는 add_todo를 통해 추가)
        self.todo1 = Todo("Task 1", "초기 할 일 1", "2026-10-01")
        self.todo2 = Todo("Task 2", "초기 할 일 2")
        self.todo3 = Todo("Task 3", "미완료 테스트 항목")
        self.manager.todos = [self.todo1, self.todo2, self.todo3]

    def test_add_todo_success(self):
        new_todo = self.manager.add_todo("New Task", "Test Desc")
        self.assertIsInstance(new_todo, Todo)
        self.assertEqual(len(self.manager.todos), 4) # 기존 3개 + 새거 1개

    def test_get_all_todos_structure(self):
        todos_list = self.manager.get_all_todos()
        self.assertEqual(len(todos_list), 3)
        # 첫 번째 항목의 구조 검증
        self.assertIn("title", todos_list[0])
        self.assertIn("is_done", todos_list[0])

    def test_complete_todo_success(self):
        # Task 1을 완료 처리 시도 (임시 ID 가정)
        success = self.manager.complete_todo(1)
        self.assertTrue(success)
        # 객체 자체를 검사하여 상태가 변경되었는지 확인 (실제로는 DB에서 로드 필요)
        # 여기서는 내부 리스트의 첫 번째 항목이 완료 상태가 되었는지 확인하는 방식으로 검증
        self.assertTrue(self.todo1.is_done)

    def test_complete_todo_already_done(self):
        # 이미 완료된 Task 1 재시도
        self.todo1.is_done = True # 강제 설정
        success = self.manager.complete_todo(1)
        self.assertFalse(success)

    def test_delete_todo_success(self):
        # Task 2를 삭제 시도 (임시 ID 가정)
        success = self.manager.delete_todo(2)
        self.assertTrue(success)
        # Task 2가 제거되었는지 검증 (리스트 크기 확인)
        self.assertEqual(len(self.manager.todos), 2)
        
    def test_delete_nonexistent_todo(self):
        # 존재하지 않는 ID 삭제 시도
        success = self.manager.delete_todo(99)
        self.assertFalse(success)
        self.assertEqual(len(self.manager.todos), 3) # 크기 변화 없음

if __name__ == '__main__':
    unittest.main()