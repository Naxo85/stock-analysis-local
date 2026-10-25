"""Receipt binding for compact input must use the same frozen policy as calls."""
from copy import deepcopy
import hashlib
import json
import unittest

from test_diff_transport import fixture
from src.local_runner.adaptive_context import model_context, serialize_model_input
from src.local_runner.diff_transport import select_transport, VERSION
from src.local_runner.semantic_binding import bind_response, require_response_binding


class BindingTests(unittest.TestCase):
    def test_exact_binding_for_all_roles_and_authority_changes_rejected(self):
        context=fixture();payload={'decision':'retain'}
        policy={'maintenance_context_transport':VERSION}
        for kind in ['triage','triage_repair','report']:
            with self.subTest(kind=kind):
                view=model_context(context)
                if kind!='report':select_transport(view,policy)
                receipt={'exit_code':0,'text':json.dumps(payload),
                    'input_sha256':hashlib.sha256(serialize_model_input(view).encode()).hexdigest()}
                binding=bind_response(context,receipt,kind,policy=policy)
                require_response_binding(payload,context,binding,report=kind=='report')
                changed=deepcopy(context);changed['slim']['latest_price']=9
                with self.assertRaisesRegex(ValueError,'frozen_authority_changed'):
                    require_response_binding(payload,changed,binding,report=kind=='report')
                if kind!='report':
                    with self.assertRaisesRegex(ValueError,'input_receipt'):
                        bind_response(context,receipt,kind)

    def test_legacy_policy_requires_legacy_receipt(self):
        context=fixture();payload={'decision':'retain'}
        view=model_context(context)
        receipt={'exit_code':0,'text':json.dumps(payload),
            'input_sha256':hashlib.sha256(serialize_model_input(view).encode()).hexdigest()}
        binding=bind_response(context,receipt,'triage')
        require_response_binding(payload,context,binding)
        with self.assertRaisesRegex(ValueError,'input_receipt'):
            bind_response(context,receipt,'triage',policy={'maintenance_context_transport':VERSION})
