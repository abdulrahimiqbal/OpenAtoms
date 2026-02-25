from core import Container

class Action:
    def __init__(self):
        self.status = "pending"

    def validate(self) -> bool:
        raise NotImplementedError

class Move(Action):
    def __init__(self, source: Container, destination: Container, amount_ml: float):
        super().__init__()
        self.source = source
        self.destination = destination
        self.amount_ml = amount_ml

    def validate(self):
        if self.source.current_volume < self.amount_ml:
            raise ValueError(f"PhysicsError: Cannot move {self.amount_ml}mL. Only {self.source.current_volume}mL available.")
        if self.destination.current_volume + self.amount_ml > self.destination.max_volume_ml:
            raise ValueError(f"PhysicsError: Exceeds max capacity of {self.destination.max_volume_ml}mL.")
        return True

class Transform(Action):
    def __init__(self, target: Container, parameter: str, target_value: float, duration_s: float):
        super().__init__()
        self.target = target
        self.parameter = parameter
        self.target_value = target_value
        self.duration_s = duration_s

    def validate(self):
        if self.parameter == "temperature_c":
            if self.target_value > self.target.max_temp_c:
                raise ValueError(f"PhysicsError: Temp {self.target_value}°C exceeds melting point of {self.target.max_temp_c}°C.")
            if self.target_value < self.target.min_temp_c:
                raise ValueError(f"PhysicsError: Temp {self.target_value}°C below minimum tolerance.")
        return True

class Combine(Action):
    def __init__(self, target: Container, method: str, duration_s: float):
        super().__init__()
        self.target = target
        self.method = method
        self.duration_s = duration_s

    def validate(self):
        if self.target.current_volume == 0:
            raise ValueError(f"LogicError: Cannot apply '{self.method}'. Container is empty.")
        return True

class Measure(Action):
    def __init__(self, target: Container, sensor_type: str):
        super().__init__()
        self.target = target
        self.sensor_type = sensor_type
        self.result = None

    def validate(self):
        return True
