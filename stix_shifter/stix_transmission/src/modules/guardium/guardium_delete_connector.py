from ..base.base_delete_connector import BaseDeleteConnector
import json
from .....utils.error_response import ErrorResponder
import logging


class GuardiumDeleteConnector(BaseDeleteConnector):
    def __init__(self, api_client):
        self.api_client = api_client

    def delete_query_connection(self, search_id):
        # Not implemented for Guardium
        #response = self.api_client.delete_search(search_id)
        #response_code = response.code
        #response_json = json.loads(response.read())
        responses = json.loads('{"message":"Not Implemented", "status":"Not Implemented","data":{"message":"Cannot delete search - Guardium does not support this request."}}')
        response_code = 501
        return_obj = dict()
        return_obj['success'] = False
        return_obj['status'] = responses.get('status',"NA")
        return_obj['progress'] = responses.get('progress',"NA")
        return_obj['data'] = responses.get('data',"NA")
        return_obj["search_id"] = search_id
        logging.info(
            "\n ===> TRANSMIT Delete \n ------------ Guardium Connector - calling delete query --------")
        logging.info(responses)
        # Verify the input
        if response_code == 202:
            return_obj['success'] = True
        else:
            ErrorResponder.fill_error(return_obj, responses, ['message'])

        return return_obj