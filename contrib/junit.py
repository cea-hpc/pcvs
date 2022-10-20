from xml.dom import xmlbuilder
from pcvs.orchestration import publishers
from pcvs.plugins import Plugin
from pcvs.testing.test import Test
from junit_xml import TestSuite, TestCase

class JUnit(Plugin):
    
    step = Plugin.Step.SCHED_PUBLISH_WRITE
    
    def run(self, *args, **kwargs):
        data = kwargs.get("data", {})
        out_prefix = kwargs.get('outfile', "./testfile") + ".xml"
        
        
        test_cases = []
        for t in data['tests']:
            fullname = t['id']['fq_name']
            state = t['result']['state']
            
            tt = TestCase(
                name=fullname,
                classname=fullname.replace("/", "."),
                elapsed_sec=t['result']['time'],
            )
            
            if state == Test.State.FAILURE:
                tt.add_failure_info(message="failure", output=t['result']['output'])
            elif state == Test.State.ERR_DEP:
                tt.add_skipped_info(message="Dependency not satisfied", output=t['result']['output'])
            elif state != Test.State.SUCCESS:
                tt.add_error_info(message="Unkown error", output=t['result']['output'], type=str(state))
        
            test_cases.append(tt)
                              
        
        ts = TestSuite("pcvs-run", test_cases)
        
        with open(out_prefix, "w") as f:
            TestSuite.to_file(f, [ts], prettyprint=False)
        