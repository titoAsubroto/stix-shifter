import json
from . import json_to_stix_translator
from ..modules.base.base_result_translator import BaseResultTranslator
from stix_shifter.stix_translation.src.utils import transformers
import logging

# Concrete BaseResultTranslator


class JSONToStix(BaseResultTranslator):

    def translate_results(self, data_source, data, options, mapping=None):
        """
        Translates JSON data into STIX results based on a mapping file
        :param data: JSON formatted data to translate into STIX format
        :type data: str
        :param mapping: The mapping file path to use as instructions on how to translate the given JSON data to STIX. 
            Defaults the path to whatever is passed into the constructor for JSONToSTIX (This should be the to_stix_map.json in the module's json directory)
        :type mapping: str (filepath)
        :return: STIX formatted results
        :rtype: str
        """
        logging.debug("translate_results")
        self.mapping = options['mapping'] if 'mapping' in options else {}
        json_data = json.loads(data)
        data_source = json.loads(data_source)
        logging.debug("\nJSONToStix - self.mapping: " + str(self.mapping))
        logging.debug("\nJSONToStix - self.default_mapping_file_path: " + str(self.default_mapping_file_path))
        if(not self.mapping):
            map_file = open(self.default_mapping_file_path).read()
            map_data = json.loads(map_file)
            logging.debug("\nmapfile: ")
            logging.debug(map_data)
        else:
            map_data = self.mapping
            logging.debug("self.mapping: ")
            logging.debug(mapfile)

        logging.debug("data_source (input): ")
        logging.debug(data_source)
        logging.debug("data_source (Json): ")
        logging.debug(data_source)
        logging.debug("data (input): ")
        logging.debug(data)
        logging.debug("json_data: ")
        logging.debug(json_data)
        results = json_to_stix_translator.convert_to_stix(data_source, map_data,
                                                          json_data, transformers.get_all_transformers(), options, self.callback)

        return json.dumps(results, indent=4, sort_keys=False)
