# SQLMesh-MCP

This is a test repo to explore ideas.

## Setup
1. Run `make install`

## Questions - How can SQLMesh Development be improved by AI?
### Impact Analysis
1. If I change this SQL Model, which downstream models are affected?
    a. If I change this column, which downstream models are affected and which columns?
2. `sqlmesh table_diff` can be expensive, how do we control cost?

### Data Context / Metadata
1. Semantic layer? What does the data look like and represent?
2. Data Types, Column Names, Model Names, etc.
3. Storing off samples of tables using relationships
    a. Check Metrics implementation

### Development Best Practices
1. Supporting good enough Data Modeling
    a. What is the grain?
        i. Supports creating/manipulating grain with aggregations
    b. What Model KIND should be chosen?
        i. Load Patterns
2. Accounting for Common Scenarios in SQL:
    a. NULLs
    b. Blank Strings
    
### Efficiency / Feedback Loop / Testing Changes
1. SQLGlot + DuckDB -> local validation
    a. Need a way to replicate upstream models' data
        i. Unit Test code already offers a micro approach
    b. Replicating data, creating fake data, creating scenarios, etc.
        i. LIMIT 100? Maybe a way to sample with a specific Seed number
    c. Better way to do than yaml?
2. Always using `start` and `end` with `plan`
3. `dev` environments
    a. Does the AI get its own dedicated `dev` environment for testing?
        i. Is that necessary if the user already has a `dev` environment?
4. We have partition and clustering columns
    a. Guiding AI in how to query models

### Validation
1. Time
    a. A way to play out multiple data loads over time (ex. `time-machine`)
        i. How many intervals should be tested by default?
2. Idempotency
    a. A way to validate / test for idempotency
        i. Run 2 (maybe 3) times to determine idempotent

### SafeGuards
1. Cannot execute commands against `prod`. AI be crazy.
2. Linting Rules must Pass
3. Changes must be validated against data

## Scope
SQLMesh encourages best practices in analytics work and data engineering by promoting best practices for idempotency, grain, time-aware models (intervals), etc. What empowers better SQLMesh use?
 - Idempotency
    - Confirming that multiple runs always produce the same result
        - Needed for proper loading of most models
 - Grain
    - Having a clear grain that accurately represents the level of detail of the model
        - Needed for `table_diff`
 - Unit Tests
    - Confirming code is tested
        - Writing tests first?
 - Audit
    - Unacceptable data scenarios
 - Lineage
    - One of SQLMesh's main feature is determining lineage between models
 - Plan Diff
    - Showing what models have changed and what that affects