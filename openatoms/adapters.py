import json

class Adapter:
    def __init__(self, dag_json: str):
        self.protocol_data = json.loads(dag_json)
    def compile(self) -> str:
        raise NotImplementedError

class OpentronsAdapter(Adapter):
    def compile(self) -> str:
        output = [
            "from opentrons import protocol_api",
            f"metadata = {{'apiLevel': '2.13', 'protocolName': '{self.protocol_data['protocol_name']}'}}",
            "def run(protocol: protocol_api.ProtocolContext):",
            "    plate = protocol.load_labware('corning_96_wellplate_360ul_flat', '1')",
            "    pipette = protocol.load_instrument('p300_single', 'right', tipracks=[])"
        ]
        for step in self.protocol_data['steps']:
            action, params = step['action_type'], step['parameters']
            if action == "Move":
                output.append(f"    pipette.transfer({params['amount_ml']}, plate.wells_by_name()['{params['source']}'], plate.wells_by_name()['{params['destination']}'])")
            elif action == "Transform" and params['parameter'] == "temperature_c":
                output.append(f"    temp_module = protocol.load_module('temperature module', '3')\n    temp_module.set_temperature({params['target_value']})")
        return "\n".join(output)

class SmartBaristaAdapter(Adapter):
    def compile(self) -> str:
        output = []
        for step in self.protocol_data['steps']:
            action, params = step['action_type'], step['parameters']
            if action == "Move":
                output.append(json.dumps({"topic": f"barista/pump/{params['source']}", "command": "dispense", "target_vessel": params['destination'], "volume_ml": params['amount_ml']}))
            elif action == "Transform" and params['parameter'] == "temperature_c":
                output.append(json.dumps({"topic": f"barista/boiler/{params['target']}", "command": "heat", "target_temp_c": params['target_value']}))
        return "\n".join(output)
