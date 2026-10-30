"""Synthetic demonstration; these values are not experimental observations."""
from workcert import ReducedResponse, reduce_response

table = reduce_response(
    [0, 1, 2, 3, 4, 5, 6, 7, 8], [0, 2, 4, 2, 3, 1, 2, 1, 0],
    max_points=5, provenance={"source": "synthetic demonstration"},
)
table.save("response.workcert.json")
loaded = ReducedResponse.load("response.workcert.json")
print("force at 3.5 mm:", loaded.force_at(3.5), loaded.force_unit)
print("work to 3.5 mm:", loaded.work(3.5), loaded.work_unit)
print("work over [1, 6] mm:", loaded.window_work(1, 6), loaded.work_unit)
print("prefix bound:", loaded.certificate.prefix, loaded.work_unit)
print("window bound:", loaded.certificate.window, loaded.work_unit)

