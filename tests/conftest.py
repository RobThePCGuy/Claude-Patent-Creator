"""Pytest configuration and shared fixtures for patent analyzer tests."""

import pytest


@pytest.fixture
def sample_claims_two_part():
    """EP-style claims with two-part form."""
    return """
1. A device for processing signals, the device comprising a receiver,
characterized in that the receiver includes a filter configured to reduce noise.

2. The device of claim 1, wherein the filter is a Kalman filter.
"""


@pytest.fixture
def sample_claims_no_two_part():
    """Claims without two-part form (US style)."""
    return """
1. A method comprising:
    a) receiving input data;
    b) processing the input data using a neural network; and
    c) outputting results.

2. The method of claim 1, wherein the neural network is a transformer.
"""


@pytest.fixture
def sample_epo_specification():
    """EPO-format specification with Rule 42 sections."""
    return """
TECHNICAL FIELD
The present invention relates to data processing systems.

BACKGROUND ART
Prior systems suffer from high latency due to sequential processing.

DISCLOSURE OF THE INVENTION
The invention provides a parallel processing pipeline that reduces latency
by partitioning input data across multiple processing units.

BRIEF DESCRIPTION OF DRAWINGS
FIG. 1 shows a system block diagram.
FIG. 2 shows the processing pipeline.

DETAILED DESCRIPTION
The system (100) includes a processor (110) connected to memory (120).
The processor executes instructions to partition incoming data streams.

INDUSTRIAL APPLICABILITY
The invention is applicable to real-time data processing in cloud computing.
"""


@pytest.fixture
def sample_good_abstract():
    """Abstract with reference signs (EPO-compliant)."""
    return (
        "A data processing system (100) includes a processor (110) connected to a memory (120) "
        "via a bus (130). The processor (110) executes instructions stored in the memory (120) "
        "to perform signal analysis on input data received from a sensor array (140). "
        "The system achieves improved throughput by employing a multi-stage pipeline (150) "
        "with parallel execution units (160) operating on partitioned data streams. "
        "Results are output through an interface module (170) to external devices."
    )
