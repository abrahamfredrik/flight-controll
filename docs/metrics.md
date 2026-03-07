# Metrics Feature Documentation

## Overview
The application records metrics for each scheduler run and uploads them to MongoDB in the `run_metrics` collection. This enables tracking of job execution, success/failure, and event change counts for observability and troubleshooting.

## Metrics Schema
Each metrics document has the following fields:

- `uuid` (str): Unique identifier for the run (UUID4).
- `start_time` (datetime): UTC timestamp when the run started.
- `stop_time` (datetime): UTC timestamp when the run ended.
- `success` (bool): True if the run completed without error, False otherwise.
- `new_count` (int): Number of new events detected.
- `updated_count` (int): Number of updated events detected.
- `removed_count` (int): Number of removed events detected.
- `error` (str, optional): Error message if the run failed, else null.

## Collection
- MongoDB collection name: `run_metrics`
- No indexes are created by default.

## How It Works
- After each scheduler run, a metrics record is created and inserted into MongoDB.
- The metrics repository (`MetricsRepository`) handles persistence.
- The scheduler job records start/stop time, counts, and error status.

## Testing
- Unit tests cover the metrics repository.
- Integration tests verify that metrics are persisted after a scheduler run.

## Usage
- To view metrics, query the `run_metrics` collection in your MongoDB instance.
- Each document represents a single scheduler run.

## Extending
- To add more fields, update the `RunMetrics` dataclass and repository logic.
- To aggregate or analyze metrics, use MongoDB queries or BI tools.
