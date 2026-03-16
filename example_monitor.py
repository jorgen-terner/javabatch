#!/bin/ksh
# 20181116 DB
# $0 start/error/stop $$
### MONITOR #######################################################
server=$(hostname -s)
#server=$NGINXHOST
if [[ $server == *"prod"* ]]; then
  metricshost=fkmetrics
  exec_db=surv_executing
  history_db=surv_history
else
  #
  metricshost=metricstest
  exec_db=davve
  history_db=davve
#  exit 0
fi
environment=jbatch
state=$1
PID=$2
starttime=$(ps -p $PID -o start=)
elapsed=$(ps -p $PID -o etime= | xargs)
if [ $(echo -n $elapsed | wc -c) -eq 5 ]; then
  elapsed=00:${elapsed}
fi
object=$(echo $TO_JOB_NAME | tr -dc [a-z,A-Z,0-9],-_)
if [ -z $object ]; then
  object=$(basename $(ps -p $PID -o command= | cut -d' ' -f2))
fi
chart=$TO_ENV_NAME
if [ -z $chart ]; then
  chart=MANUELL
fi

monitor()       {
  case $state in
    start)
      objectstatus=Executing
      statusflag=0
      influxdb=$exec_db
      $dbdrop
      $dbinsert
      ;;
    error)
      objectstatus=Failed
      statusflag=1
      influxdb=$history_db
      $dbdrop
      $dbinsert
      ;;
    stop)
      objectstatus=Completed
      statusflag=2
      influxdb=$history_db
      $dbdrop
      $dbinsert
esac

  dbdrop=$(curl -s -XPOST 'http://'${metricshost}'.sfa.se:8086/query?db='${exec_db}'' --data-binary "q=DROP SERIES from exec_job where JOB='$object'")
  dbinsert=$(curl -s -XPOST 'http://'${metricshost}'.sfa.se:8086/write?db='${influxdb}'' --data-ascii 'exec_job,JOB='${object}' Object="'${object}'",Start_time="'${starttime}'",Status="'${objectstatus}'",PID='${PID}',User="'${LOGNAME}'",Server="'${server}'",Chart="'${chart}'",Environment="'${environment}'",Elapsed="'${elapsed}'",Status_flag='$statusflag'')
  }

monitor
