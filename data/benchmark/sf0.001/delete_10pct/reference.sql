WITH lineitem AS (SELECT l.* FROM main.lineitem l WHERE NOT EXISTS (SELECT 1 FROM removed d WHERE d.l_orderkey=l.l_orderkey AND d.l_linenumber=l.l_linenumber)) SELECT l_orderkey, o_orderdate, o_shippriority,
       sum(l_extendedprice * (1 - l_discount)) AS revenue
FROM customer, orders, lineitem
WHERE c_mktsegment = 'AUTOMOBILE'
  AND c_custkey = o_custkey
  AND l_orderkey = o_orderkey
  AND o_orderdate < DATE '1995-03-13'
  AND l_shipdate > DATE '1995-03-13'
GROUP BY l_orderkey, o_orderdate, o_shippriority;
