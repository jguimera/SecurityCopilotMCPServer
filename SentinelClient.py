import pandas as pd 
from azure.monitor.query import LogsQueryClient,LogsQueryStatus
from azure.core.exceptions import HttpResponseError
class SentinelClient:
    login_url="https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    API_url="https://management.azure.com/subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/Microsoft.OperationalInsights/workspaces/{workspaceName}/providers/Microsoft.SecurityInsights/"
    API_query_url="https://management.azure.com/subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/Microsoft.OperationalInsights/workspaces/{workspaceName}/providers/Microsoft.Insights/"
    API_management_url="https://management.azure.com"
    API_versionOLD="2021-03-01-preview"
    API_version_incidents="2021-04-01"
    API_version_rules="2021-10-01"
    API_version_logs="2018-08-01-preview"
    API_version_templates="2023-02-01"
    scope="https://management.azure.com/.default"

    def __init__(self,credential,subscriptionId,resourceGroupName,workspaceName,workspace_id):

        self.subscriptionId = subscriptionId
        self.resourceGroupName = resourceGroupName
        self.workspaceName = workspaceName
        self.workspace_id=workspace_id
        self.access_token_timestamp=0
        self.credential=credential
        self.logs_client=LogsQueryClient(self.credential)

    def run_query(self,query,printresults=False):
        results_object={}
        try:
            response = self.logs_client.query_workspace(
                workspace_id=self.workspace_id,
                query=query,
                timespan=None
                )
            if response.status == LogsQueryStatus.PARTIAL:
                error = response.partial_error
                data = response.partial_data
                print(error.message)
            elif response.status == LogsQueryStatus.SUCCESS:
                data = response.tables
            for table in data:
                df = pd.DataFrame(data=table.rows, columns=table.columns)
                if printresults:
                    print(df)
                results_object={"status":"success","result":df.to_dict(orient="records")}
        except HttpResponseError as err:
            results_object={"status":"error","result":err}
        return results_object