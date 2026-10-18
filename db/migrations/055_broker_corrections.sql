BEGIN;
CREATE OR REPLACE FUNCTION ack(p_group_name text,p_locations jsonb) RETURNS integer
LANGUAGE plpgsql AS $$
DECLARE v_group bigint; v_partition bigint; v_count integer; v_total integer:=0; v_next bigint;
BEGIN
 SELECT group_id INTO v_group FROM consumer_group WHERE group_name=p_group_name;
 IF v_group IS NULL THEN RAISE EXCEPTION 'unknown group %',p_group_name USING ERRCODE='CDT06'; END IF;
 FOR v_partition IN SELECT DISTINCT e.partition_id FROM jsonb_to_recordset(COALESCE(p_locations,'[]'))
   AS e(partition_id bigint,msg_offset bigint) ORDER BY e.partition_id
 LOOP
   -- Serialize offset changes before updating the corresponding message rows.
   PERFORM 1 FROM group_offset WHERE group_id=v_group AND partition_id=v_partition FOR UPDATE;
   UPDATE message m SET status='delivered'
   WHERE m.partition_id=v_partition AND m.claimed_by=v_group AND m.status='claimed'
     AND EXISTS(SELECT 1 FROM jsonb_to_recordset(COALESCE(p_locations,'[]')) AS e(partition_id bigint,msg_offset bigint)
                WHERE e.partition_id=m.partition_id AND e.msg_offset=m.msg_offset);
   GET DIAGNOSTICS v_count=ROW_COUNT;
   v_total:=v_total+v_count;
   SELECT COALESCE(min(m.msg_offset),pt.next_offset) INTO v_next
   FROM partition pt LEFT JOIN message m ON m.partition_id=pt.partition_id AND m.status NOT IN ('delivered','dead')
   WHERE pt.partition_id=v_partition GROUP BY pt.next_offset;
   UPDATE group_offset SET committed_offset=GREATEST(committed_offset,v_next),updated_at=now()
   WHERE group_id=v_group AND partition_id=v_partition;
 END LOOP;
 RETURN v_total;
END $$;
COMMIT;
