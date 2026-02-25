import json
from typing import List
from actions import Action, Move, Transform

class ProtocolGraph:
    def __init__(self, name: str):
        self.name = name
        self.sequence: List[Action] = []
        self.is_compiled = False

    def add_step(self, action: Action):
        self.sequence.append(action)

    def dry_run(self) -> bool:
        print(f"--- Starting Dry Run for Protocol: {self.name} ---")
        for step_index, action in enumerate(self.sequence):
            try:
                action.validate()
                if isinstance(action, Move):
                    from core import Matter, Phase
                    transferred_matter = Matter("mixture", Phase.LIQUID, 0, action.amount_ml)
                    if action.source.contents: action.source.contents.pop()
                    action.destination.contents.append(transferred_matter)
                elif isinstance(action, Transform):
                    if action.parameter == "temperature_c":
                        for matter in action.target.contents: matter.temp_c = action.target_value
                print(f"[✓] Step {step_index + 1} Validated: {type(action).__name__}")
            except ValueError as e:
                print(f"[X] LINTER FATAL ERROR at Step {step_index + 1}: {e}")
                return False
        self.is_compiled = True
        return True

    def export_json(self) -> str:
        if not self.is_compiled: raise RuntimeError("Must pass dry_run() first.")
        payload = {"protocol_name": self.name, "version": "1.0.0", "steps": []}
        for i, action in enumerate(self.sequence):
            step_data = {
                "step": i + 1,
                "action_type": type(action).__name__,
                "parameters": {k: v.name if hasattr(v, 'name') else v for k, v in vars(action).items() if k != 'status'}
            }
            payload["steps"].append(step_data)
        return json.dumps(payload, indent=4)
