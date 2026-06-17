import unittest
from unittest.mock import MagicMock, patch
from Agent import AgentOrchestrator, AgentTurn, OllamaClient

class AgentOrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock(spec=OllamaClient)
        # Mock base_url for error reporting
        self.mock_client.base_url = "http://localhost:11434/api"
        self.orchestrator = AgentOrchestrator(client=self.mock_client)

    def test_parse_response_valid_json(self):
        json_text = '{"thought": "I should lock the screen", "action": "press", "input": {"keys": ["alt", "l"]}}'
        turn = self.orchestrator._parse_response(json_text)
        self.assertEqual(turn.thought, "I should lock the screen")
        self.assertEqual(turn.action_name, "press")
        self.assertEqual(turn.action_input, {"keys": ["alt", "l"]})

    def test_parse_response_with_extra_text(self):
        text = 'Sure, here is the action: {"thought": "Thinking...", "action": "move", "input": {"x": 10, "y": 20}} hope that helps!'
        turn = self.orchestrator._parse_response(text)
        self.assertEqual(turn.action_name, "move")
        self.assertEqual(turn.action_input, {"x": 10, "y": 20})

    def test_parse_response_invalid_json_falls_back_to_thought(self):
        text = "I don't know how to do that yet."
        turn = self.orchestrator._parse_response(text)
        self.assertEqual(turn.thought, text)
        self.assertIsNone(turn.action_name)

    @patch("FionaCore.ActionRouter.run")
    def test_execute_action_mapping_launch(self, mock_run):
        mock_result = MagicMock()
        mock_result.ok = True
        mock_result.message = "Launched"
        mock_run.return_value = mock_result
        
        observation = self.orchestrator._execute_action("launch_binding", {"name": "terminal"})
        mock_run.assert_called_with("launch:terminal", source="agent")
        self.assertIn("Status: Success", observation)

    @patch("FionaCore.ActionRouter.run")
    def test_execute_action_generic_mapping(self, mock_run):
        mock_result = MagicMock()
        mock_result.ok = False
        mock_result.message = "Failed to click"
        mock_run.return_value = mock_result
        
        params = {"button": "left", "x": 100, "y": 100}
        observation = self.orchestrator._execute_action("click", params)
        import json
        mock_run.assert_called_with(f"click:{json.dumps(params)}", source="agent")
        self.assertIn("Status: Failed", observation)

    def test_run_goal_finishes_on_null_action(self):
        self.mock_client.ask.return_value = '{"thought": "Task complete!", "action": null}'
        
        result = self.orchestrator.run_goal("dummy goal")
        self.assertEqual(result, "Task complete!")
        self.assertEqual(len(self.orchestrator.history), 1)

if __name__ == "__main__":
    unittest.main()
