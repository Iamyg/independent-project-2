# First-stage experimental results

Generated from saved Flink job and comparison records.

Total: 28 scenarios; passed: 28.

| Category | Scenario | Status | Input events | Expected groups | Actual groups | Maximum absolute amount error |
|---|---|---|---:|---:|---:|---:|
| micro | 01_no_detail | passed | 2 | 0 | 0 | 0 |
| micro | 02_one_detail | passed | 3 | 1 | 1 | 0.0000 |
| micro | 03_two_details | passed | 4 | 1 | 1 | 0.0000 |
| micro | 04_delete_detail | passed | 5 | 1 | 1 | 0.0000 |
| micro | 05_delete_customer | passed | 6 | 0 | 0 | 0 |
| micro | 06_restore_customer | passed | 7 | 1 | 1 | 0.0000 |
| micro | 07_delete_order | passed | 5 | 0 | 0 | 0 |
| micro | 08_restore_order | passed | 6 | 1 | 1 | 0.0000 |
| micro | 09_delete_last_detail | passed | 4 | 0 | 0 | 0 |
| micro | 10_late_parents | passed | 4 | 1 | 1 | 0.0000 |
| micro | 11_wrong_segment | passed | 3 | 0 | 0 | 0 |
| micro | 12_order_date_boundary | passed | 3 | 0 | 0 | 0 |
| micro | 13_ship_date_boundary | passed | 3 | 0 | 0 | 0 |
| micro | 14_future_order | passed | 3 | 0 | 0 | 0 |
| micro | 15_early_shipment | passed | 3 | 0 | 0 | 0 |
| micro | 16_missing_customer | passed | 3 | 0 | 0 | 0 |
| micro | 17_missing_order | passed | 3 | 0 | 0 | 0 |
| micro | 18_two_orders | passed | 5 | 2 | 2 | 0.0000 |
| micro | 19_delete_filtered_detail | passed | 5 | 1 | 1 | 0.0000 |
| micro | 20_delete_reinsert_detail | passed | 5 | 1 | 1 | 0.0000 |
| micro | 21_update_discount | passed | 5 | 1 | 1 | 0.0000 |
| micro | 22_change_customer_segment | passed | 5 | 0 | 0 | 0 |
| tpch | insert | passed | 7655 | 11 | 11 | 1E-11 |
| tpch | delete_lineitems | passed | 7658 | 10 | 10 | 1E-11 |
| tpch | delete_order | passed | 7656 | 10 | 10 | 1E-11 |
| tpch | delete_customer | passed | 7656 | 9 | 9 | 1E-11 |
| tpch | mixed_restore | passed | 7660 | 10 | 10 | 1E-11 |
| tpch | late_parents | passed | 7655 | 11 | 11 | 1E-11 |

## Expected answers and verification

Order 101 lifecycle prefixes expect: no group -> 900 -> 1300 -> 400 -> no group -> 400. Each prefix is an independent replay from empty state; final results are checked after FINISHED against SQL and hand calculations.

Require identical group keys. Amount tolerance is max(1e-6, 1e-9 * abs(reference)); Cquirrel uses Double and the SQL oracle uses DECIMAL.

Near-zero final groups are recorded as empty-group sentinels. This assumes strictly positive contributions and is not a general SUM solution.

## Artifacts and scope

The retained chain is SQL -> plan -> Scala -> JAR -> Flink job -> raw output -> independent SQL answer -> comparison.

Inputs use +CU/-CU, +OR/-OR and +LI/-LI for customer, order and line-item updates. Query constants are AUTOMOBILE and 1995-03-13.

First-stage timings document execution only. Repeated timing experiments are reported separately in results/latest-benchmark.json and the final report. Q5 scalability, recovery and GUI reproduction are outside scope.

See FILES.md for artifact roles and ../README.md for commands.

## TPC-H input

Generator: DuckDB 1.1.3 with the signed official TPC-H extension, SF=0.001.

Rows: {'CU': 150, 'OR': 1500, 'LI': 6005}. Initial Q3 groups: 11.

The database, three original table files, update streams and generation metadata are stored under data/tpch/.
