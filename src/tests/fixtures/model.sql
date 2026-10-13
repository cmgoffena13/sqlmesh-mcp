MODEL (
  name pkg.mod,
  kind FULL
);
SELECT {{ 1 }} AS id, @FOO(1) AS other
