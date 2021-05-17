from flee import flee
from flee.datamanager import handle_refugee_data
import numpy as np
import flee.postprocessing.analysis as a

"""
Generation 1 code. Incorporates only distance, travel always takes one day.
"""


def test_removelink():
    print("Testing basic data handling and simulation kernel.")

    end_time = 80
    e = flee.Ecosystem()

    l1 = e.addLocation("A", movechance=0.3)

    l2 = e.addLocation("B", movechance=0.0)
    l3 = e.addLocation("C", movechance=0.0)
    l4 = e.addLocation("D", movechance=0.0)

    e.linkUp("A", "B", "834.0")
    e.linkUp("A", "C", "1368.0")
    e.linkUp("A", "D", "536.0")

    assert e.remove_link("A", "C")

    print("Test successful!")


if __name__ == "__main__":
    test_removelink()
