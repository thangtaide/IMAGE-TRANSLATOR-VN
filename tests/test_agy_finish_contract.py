"""Synthetic contract of the schema completion captured from CLI1.5.3."""
import json
import unittest
from providers.agy import parse_response, output_schema, SESSION_SETTINGS
from providers.online import OnlineProviderError


class FinishContractTests(unittest.TestCase):
    def events(self, whole=False):
        row = {'region_id': 'qa1', 'translated_text': 'Chương 13'} if whole else {'id': 'qa1', 'text': 'Chương 13'}
        answer = {'translations': [row]}
        return [dict(event='step_update',step_update=dict(conversation_id='qa',step_index=1,
                    state='ACTIVE',step_type='tool',tool_name='finish',
                    tool_info=dict(name='finish',parameters=answer))),
                dict(event='result',result=dict(status='SUCCESS',num_turns=1,
                    response=json.dumps(answer),structured_output=answer,json_schema=output_schema(['qa1'],whole=whole)))]

    def parse(self, events, whole=False):
        return parse_response(('\n'.join(json.dumps(e) for e in events)).encode(), ['qa1'], 0, whole=whole)

    def test_exact_structured_finish_is_completion_for_batch_and_whole(self):
        for whole in (False, True):
            self.assertEqual(self.parse(self.events(whole),whole), ['Chương 13'])

    def test_denied_read_is_still_rejected_even_with_valid_finish(self):
        events=self.events()
        events.insert(0,dict(event='step_update',step_update=dict(state='ERROR',step_type='tool',
            tool_name='read_file',tool_info=dict(name='read_file',error={'type':'PERMISSION_DENIED'}))))
        with self.assertRaises(OnlineProviderError):self.parse(events)

    def test_finish_without_exact_schema_or_matching_payload_rejected(self):
        for field in ('json_schema','structured_output'):
            events=self.events();events[-1]['result'].pop(field)
            with self.assertRaises(OnlineProviderError):self.parse(events)
        events=self.events();events[0]['step_update']['tool_info']['parameters']= {'other':'payload'}
        with self.assertRaises(OnlineProviderError):self.parse(events)

    def test_extra_tool_indicators_and_arguments_cannot_hide_in_finish(self):
        for where in ('step','info','parameters'):
            events=self.events();step=events[0]['step_update']
            target=step if where=='step' else step['tool_info'] if where=='info' else step['tool_info']['parameters']
            target['tool_call']={'name':'run_command'}
            with self.assertRaises(OnlineProviderError):self.parse(events)

    def test_file_shell_web_mcp_names_never_exempt(self):
        for name in ('read_file','run_command','read_url','mcp','write_file'):
            events=self.events();events[0]['step_update']['tool_name']=name
            with self.assertRaises(OnlineProviderError):self.parse(events)

    def test_default_mode_does_not_inject_plan_and_permissions_stay_denied(self):
        self.assertEqual(SESSION_SETTINGS['agentMode'],'')
        self.assertEqual(SESSION_SETTINGS['toolPermission'],'strict')
        self.assertEqual(SESSION_SETTINGS['permissions']['allow'],[])
        self.assertIn('read_file(*)',SESSION_SETTINGS['permissions']['deny'])


if __name__=='__main__':unittest.main()
