from stix_shifter.stix_translation.src.patterns.pattern_objects import ObservationExpression, ComparisonExpression, \
    ComparisonExpressionOperators, ComparisonComparators, Pattern, \
    CombinedComparisonExpression, CombinedObservationExpression, ObservationOperators
from stix_shifter.stix_translation.src.transformers import TimestampToMilliseconds
from stix_shifter.stix_translation.src.transformers import EpochToGuardium
from stix_shifter.stix_translation.src.json_to_stix import observable
from stix_shifter.stix_translation.src.stix_pattern_parser import parse_stix
from stix_shifter.stix_translation.src import transformers
import logging
import re
import json

# Source and destination reference mapping for ip and mac addresses.
# Change the keys to match the data source fields. The value array indicates the possible data type that can come into from field.
#REFERENCE_DATA_TYPES = {"QUERY_FROM_DATE": ["start"],
#                        "QUERY_TO_DATE": ["end"],"OSUser":["%"],"DBUser":"newuser",
#                        "SHOW_ALIASES":["TRUE","FALSE"],"REMOTE_SOURCE":["%"]}
REFERENCE_DATA_TYPES = {}

logger = logging.getLogger(__name__)


class QueryStringPatternTranslator:
    # Change comparator values to match with supported data source operators
    comparator_lookup = {
        ComparisonExpressionOperators.And: "AND",
        ComparisonExpressionOperators.Or: "OR",
#        ComparisonComparators.GreaterThan: ">",
#        ComparisonComparators.GreaterThanOrEqual: ">=",
#        ComparisonComparators.LessThan: "<",
#        ComparisonComparators.LessThanOrEqual: "<=",
        ComparisonComparators.Equal: "=",
#        ComparisonComparators.NotEqual: "!=",
#        ComparisonComparators.Like: "LIKE",
#        ComparisonComparators.In: "IN",
#        ComparisonComparators.Matches: 'LIKE',
        # ComparisonComparators.IsSubSet: '',
        # ComparisonComparators.IsSuperSet: '',
        ObservationOperators.Or: 'OR',
        # Treat AND's as OR's -- Unsure how two ObsExps wouldn't cancel each other out.
        ObservationOperators.And: 'OR'
    }

    def __init__(self, pattern: Pattern, data_model_mapper):
        self.dmm = data_model_mapper
        self.pattern = pattern
        self.reportParamsPassed = {}
        self.translated = self.parse_expression(pattern)
        self.transformers = transformers.get_all_transformers()
        #Read reference data
        with open("./stix_shifter/stix_translation/src/modules/guardium/json/reference_data_types4Query.json", 'r') as f_ref:
            self.REFERENCE_DATA_TYPES = json.loads(f_ref.read())
        REFERENCE_DATA_TYPES = self.REFERENCE_DATA_TYPES

        #Read reference data
        with open("./stix_shifter/stix_translation/src/modules/guardium/json/guardium_report_params.json", 'r') as f_rep:
            self.REPORT_PARAMS = json.loads(f_rep.read())


    def get_report_params(self):
        dataCategory = (self.reportParamsPassed).get("datacategory", None)

        if(dataCategory is not None):
            logging.debug(json.dumps(self.REPORT_PARAMS, indent=4))
            if 'audit' not in self.REPORT_PARAMS:
                logging.debug("Map for Data Category: " + dataCategory + " is missing")
                reportHeader = None
            else:
                reportHeader = self.REPORT_PARAMS[dataCategory]
            #replace
            logging.debug(reportHeader)
            for param in reportHeader["reportParameter"]:
                if param not in self.reportParamsPassed:
                    reportHeader["reportParameter"][param] = reportHeader["reportParameter"][param]["default"]
                else:
                    if "transformer" in reportHeader["reportParameter"][param]:
                        transformer = self.transformers[reportHeader["reportParameter"][param]["transformer"]]
                        reportHeader["reportParameter"][param] = transformer.transform(self.reportParamsPassed[param])
                    else:
                        reportHeader["reportParameter"][param] = self.reportParamsPassed[param]

        return reportHeader

    @staticmethod
    def _format_set(values) -> str:
        gen = values.element_iterator()
        return "({})".format(' OR '.join([QueryStringPatternTranslator._escape_value(value) for value in gen]))

    @staticmethod
    def _format_match(value) -> str:
        raw = QueryStringPatternTranslator._escape_value(value)
        if raw[0] == "^":
            raw = raw[1:]
        else:
            raw = ".*" + raw
        if raw[-1] == "$":
            raw = raw[0:-1]
        else:
            raw = raw + ".*"
        return "\'{}\'".format(raw)

    @staticmethod
    def _format_equality(value) -> str:
        return '\'{}\''.format(value)

    @staticmethod
    def _format_like(value) -> str:
        value = "'%{value}%'".format(value=value)
        return QueryStringPatternTranslator._escape_value(value)

    @staticmethod
    def _escape_value(value, comparator=None) -> str:
        if isinstance(value, str):
            return '{}'.format(value.replace('\\', '\\\\').replace('\"', '\\"').replace('(', '\\(').replace(')', '\\)'))
        else:
            return value

    @staticmethod
    def _negate_comparison(comparison_string):
        return "NOT({})".format(comparison_string)

    @staticmethod
    def _check_value_type(value):
        value = str(value)
        for key, pattern in observable.REGEX.items():
            if key != 'date' and bool(re.search(pattern, value)):
                return key
        return None

    @staticmethod
    def _parse_reference(self, stix_field, value_type, mapped_field, value, comparator):
        if value_type not in REFERENCE_DATA_TYPES["{}".format(mapped_field)]:
            return None
        else:
            return "{mapped_field} {comparator} {value}".format(
                mapped_field=mapped_field, comparator=comparator, value=value)

    @staticmethod
    def _parse_mapped_fields(self, expression, value, comparator, stix_field, mapped_fields_array):
        comparison_string = ""
        is_reference_value = self._is_reference_value(stix_field)
        # Need to use expression.value to match against regex since the passed-in value has already been formated.
        value_type = self._check_value_type(expression.value) if is_reference_value else None
        mapped_fields_count = 1 if is_reference_value else len(mapped_fields_array)

        for mapped_field in mapped_fields_array:
            if is_reference_value:
                parsed_reference = self._parse_reference(self, stix_field, value_type, mapped_field, value, comparator)
                if not parsed_reference:
                    continue
                comparison_string += parsed_reference
            else:
                comparison_string += "{mapped_field} {comparator} {value}".format(mapped_field=mapped_field, comparator=comparator, value=value)
                self.reportParamsPassed[mapped_field] = str(value).replace("'","",10)

            if (mapped_fields_count > 1):
                comparison_string += " OR "
                mapped_fields_count -= 1
        #print("Comparison String: " + comparison_string)

        return comparison_string

    @staticmethod
    def _is_reference_value(stix_field):
        return stix_field == 'src_ref.value' or stix_field == 'dst_ref.value'

    def _parse_expression(self, expression, qualifier=None) -> str:
        if isinstance(expression, ComparisonExpression):  # Base Case
            # Resolve STIX Object Path to a field in the target Data Model
            stix_object, stix_field = expression.object_path.split(':')
            # Multiple data source fields may map to the same STIX Object
            mapped_fields_array = self.dmm.map_field(stix_object, stix_field)
            # Resolve the comparison symbol to use in the query string (usually just ':')
            comparator = self.comparator_lookup[expression.comparator]

            if stix_field == 'start' or stix_field == 'end':
                #transformer = TimestampToGuardium()
                transformer = TimestampToMilliseconds()
                expression.value = transformer.transform(expression.value)

            # Some values are formatted differently based on how they're being compared
            if expression.comparator == ComparisonComparators.Matches:  # needs forward slashes
                value = self._format_match(expression.value)
            # should be (x, y, z, ...)
            elif expression.comparator == ComparisonComparators.In:
                value = self._format_set(expression.value)
            elif expression.comparator == ComparisonComparators.Equal or expression.comparator == ComparisonComparators.NotEqual:
                # Should be in single-quotes
                value = self._format_equality(expression.value)
            # '%' -> '*' wildcard, '_' -> '?' single wildcard
            elif expression.comparator == ComparisonComparators.Like:
                value = self._format_like(expression.value)
            else:
                value = self._escape_value(expression.value)

            comparison_string = self._parse_mapped_fields(self, expression, value, comparator, stix_field, mapped_fields_array)
            if(len(mapped_fields_array) > 1 and not self._is_reference_value(stix_field)):
                # More than one data source field maps to the STIX attribute, so group comparisons together.
                grouped_comparison_string = "(" + comparison_string + ")"
                comparison_string = grouped_comparison_string

            if expression.comparator == ComparisonComparators.NotEqual:
                comparison_string = self._negate_comparison(comparison_string)

            if expression.negated:
                comparison_string = self._negate_comparison(comparison_string)
            if qualifier is not None:
                return "{} {}".format(comparison_string, qualifier)
            else:
                return "{}".format(comparison_string)

        elif isinstance(expression, CombinedComparisonExpression):
            operator = self.comparator_lookup[expression.operator]
            expression_01 = self._parse_expression(expression.expr1)
            expression_02 = self._parse_expression(expression.expr2)
            if not expression_01 or not expression_02:
                return ''
            if isinstance(expression.expr1, CombinedComparisonExpression):
                expression_01 = "({})".format(expression_01)
            if isinstance(expression.expr2, CombinedComparisonExpression):
                expression_02 = "({})".format(expression_02)
            query_string = "{} {} {}".format(expression_01, operator, expression_02)
            if qualifier is not None:
                return "{} {}".format(query_string, qualifier)
            else:
                return "{}".format(query_string)
        elif isinstance(expression, ObservationExpression):
            return self._parse_expression(expression.comparison_expression, qualifier)
        elif hasattr(expression, 'qualifier') and hasattr(expression, 'observation_expression'):
            if isinstance(expression.observation_expression, CombinedObservationExpression):
                operator = self.comparator_lookup[expression.observation_expression.operator]
                # qualifier only needs to be passed into the parse expression once since it will be the same for both expressions
                return "{expr1} {operator} {expr2}".format(expr1=self._parse_expression(expression.observation_expression.expr1),
                                                           operator=operator,
                                                           expr2=self._parse_expression(expression.observation_expression.expr2, expression.qualifier))
            else:
                return self._parse_expression(expression.observation_expression.comparison_expression, expression.qualifier)
        elif isinstance(expression, CombinedObservationExpression):
            operator = self.comparator_lookup[expression.operator]
            expression_01 = self._parse_expression(expression.expr1)
            expression_02 = self._parse_expression(expression.expr2)
            if expression_01 and expression_02:
                return "({}) {} ({})".format(expression_01, operator, expression_02)
            elif expression_01:
                return "{}".format(expression_01)
            elif expression_02:
                return "{}".format(expression_02)
            else:
                return ''
        elif isinstance(expression, Pattern):
            return "{expr}".format(expr=self._parse_expression(expression.expression))
        else:
            raise RuntimeError("Unknown Recursion Case for expression={}, type(expression)={}".format(
                expression, type(expression)))

    def parse_expression(self, pattern: Pattern):
        return self._parse_expression(pattern)


def translate_pattern(pattern: Pattern, data_model_mapping):
    logging.debug("\nTranslate Pattern: ")
    logging.debug(pattern)
    logging.debug("\ndata model mapping: ")
    logging.debug(data_model_mapping)
                        # Converting query object to datasource query
    parsed_stix = parse_stix(pattern)
    logging.debug("\nparsed_stix: ")
    logging.debug(parsed_stix)
    guardiumQueryTranslator = QueryStringPatternTranslator(pattern, data_model_mapping)
    reportCall = guardiumQueryTranslator.translated
    reportParams = guardiumQueryTranslator.get_report_params()
    logging.debug("Report Call Header: ")
    logging.debug(reportCall)
    logging.debug("Report params Header: ")
    logging.debug(json.dumps(reportParams, indent=4))
    # Add space around START STOP qualifiers
    reportCall = re.sub("START", "START ", reportCall)
    reportCall = re.sub("STOP", " STOP ", reportCall)

    # Change return statement as required to fit with data source query language.
    # If supported by the language, a limit on the number of results may be desired.
    # A single query string, or an array of query strings may be returned
    return "{}".format(reportCall)
