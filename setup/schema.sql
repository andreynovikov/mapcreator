CREATE TABLE maps (
    area character varying(7) NOT NULL,
    size integer DEFAULT 0 NOT NULL,
    cost integer DEFAULT 0 NOT NULL,
    created integer DEFAULT 0 NOT NULL,
    error boolean DEFAULT false NOT NULL
);

ALTER TABLE ONLY maps
    ADD CONSTRAINT maps_pkey PRIMARY KEY (area);

CREATE INDEX maps_created ON maps USING btree (created);

CREATE TABLE map_downloads (
    month integer NOT NULL,
    area character varying(7) NOT NULL,
    downloads real
);

ALTER TABLE ONLY map_downloads
    ADD CONSTRAINT map_downloads_pkey PRIMARY KEY (month, area);

CREATE INDEX map_downloads_month ON map_downloads USING btree (month);

CREATE OR REPLACE FUNCTION popular_map(percent real, period interval) RETURNS TABLE(area text, created date)
AS $$
  SELECT * FROM (
    SELECT maps.area, (date '1970-01-01' + created * interval '1 day')::date AS created FROM (
      SELECT area, percent_rank() OVER (ORDER BY downloads DESC) AS pct FROM (
        SELECT area, SUM(downloads) AS downloads FROM map_downloads
        WHERE month >= (date_part('year', now() - interval '2 months') * 100 + date_part('month', now() - interval '2 months'))::integer
        GROUP BY area
      ) AS areas
    ) AS areas
    INNER JOIN maps ON (areas.area = maps.area)
    WHERE pct < $1 AND size > 0 AND error = FALSE
  ) AS areas
  WHERE age(created) > $2
  ORDER BY created
$$
LANGUAGE SQL STABLE STRICT;

CREATE OR REPLACE FUNCTION downloaded_map(period interval) RETURNS TABLE(area text, created date)
AS $$
  SELECT * FROM (
    SELECT maps.area, (date '1970-01-01' + created * interval '1 day')::date AS created FROM (
      SELECT area FROM map_downloads
      WHERE month >= (date_part('year', now() - interval '2 months') * 100 + date_part('month', now() - interval '2 months'))::integer
      GROUP BY area
    ) AS areas
    INNER JOIN maps ON (areas.area = maps.area)
    WHERE size > 0 AND error = FALSE
  ) AS areas
  WHERE age(created) > $1
  ORDER BY created
$$
LANGUAGE SQL STABLE STRICT;

CREATE OR REPLACE FUNCTION any_map(period interval) RETURNS TABLE(area text, created date)
AS $$
  SELECT * FROM (
    SELECT area, (date '1970-01-01' + created * interval '1 day')::date AS created FROM maps
    WHERE size > 0 AND error = FALSE
  ) AS areas
  WHERE age(created) > $1
  ORDER BY created
$$
LANGUAGE SQL STABLE STRICT;

CREATE OR REPLACE FUNCTION empty_map(period interval) RETURNS TABLE(area text, created date)
AS $$
  SELECT * FROM (
    SELECT area, (date '1970-01-01' + created * interval '1 day')::date AS created FROM maps
    WHERE error = FALSE
  ) AS areas
  WHERE age(created) > $1
  ORDER BY created
$$
LANGUAGE SQL STABLE STRICT;
