SELECT l_orderkey, o_orderdate, o_shippriority,
       sum(l_extendedprice * (1 - l_discount)) AS revenue
FROM customer, orders, lineitem
WHERE c_mktsegment = 'AUTOMOBILE'
  AND c_custkey = o_custkey
  AND l_orderkey = o_orderkey
  AND o_orderdate < DATE '1995-03-13'
  AND l_shipdate > DATE '1995-03-13'
GROUP BY l_orderkey, o_orderdate, o_shippriority;
