SELECT DISTINCT hostname
    , is_prod
    , hardware_type
    , hardware_model
    , os_type
    , DESCRIPTION
    , program_office
    , directorate AS host_directorate
    , FISMA_App_name
    , FISMA_SubApp_name
    , Appt_Team_name
    , LOCATION
    , DMZ

FROM cmdb_hosts
WHERE decommissioned = 'N';