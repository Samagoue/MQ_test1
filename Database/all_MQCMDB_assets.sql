SELECT DISTINCT MQ_host,
    MQmanager,
    asset,
    asset_type,
    extrainfo,
    -- directorate,
    CASE
        WHEN LOWER(directorate) LIKE 'taspd%'
        OR LOWER(MQmanager) LIKE 'qm_ats%' THEN 'TASPD'
        WHEN LOWER(MQmanager) LIKE 'qm_dhs%' THEN 'DHSRTR'
        ELSE directorate
    END as directorate,
    CASE asset_type
        WHEN 'CHANNEL' THEN
            CASE
                -- Check for cluster types first (most specific)
                WHEN LOWER(extrainfo) REGEXP '(^|\\W)(clussdr|cluster\\s+sdr|cluster\\s+sender)($|\\W)'
                    THEN 'Cluster Sender'
                WHEN LOWER(extrainfo) REGEXP '(^|\\W)(clusrcvr|cluster\\s+rcvr|cluster\\s+receiver)($|\\W)'
                    THEN 'Cluster Receiver'
               
                -- Check for connection types
                WHEN LOWER(extrainfo) REGEXP '(^|\\W)(clntconn|client\\s+conn)($|\\W)'
                    THEN 'Client Connection'
                WHEN LOWER(extrainfo) REGEXP '(^|\\W)(svrconn|server\\s+conn)($|\\W)'
                    THEN 'Server Connection'
               
                -- Check for generic sender/receiver (less specific, so checked last)
                WHEN LOWER(extrainfo) REGEXP '(^|\\W)(sender|sdr)($|\\W)'
                    THEN 'Sender'
                WHEN LOWER(extrainfo) REGEXP '(^|\\W)(receiver|rcvr)($|\\W)'
                    THEN 'Receiver'
               
                -- Default if no pattern matches
                ELSE 'Unknown'
            END
        ELSE ''
    END AS Role,
    impact,
    APPGroup,
    maillist,
    ticketsystem,
    ticketbucket,
    MQgroup,
    environment,
    snow_app_code
FROM myTable
WHERE stillvalid = 'Y';