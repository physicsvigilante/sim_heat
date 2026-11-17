"""Offline nonphysical SVG/HTML viewer source and evidence refusals."""
from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
from html.parser import HTMLParser
import re
import unittest
from unittest import mock
from xml.etree import ElementTree as ET

from h1 import reference, matv4
from tools import h1_native_batch
from qualification.h1_c1.f02 import offline_nonphysical_schematic_viewer as viewer


class _HtmlSummary(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tag_counts={}
        self.options=[]
        self.ids=[]
        self.asset_sources=[]
        self.inputs=[]
        self.inline_scripts=[]
        self._inside_script=False

    def handle_starttag(self,tag,attrs):
        self.tag_counts[tag]=self.tag_counts.get(tag,0)+1
        d=dict(attrs)
        if "id" in d:
            self.ids.append(d["id"])
        if tag=="option":
            self.options.append(d)
        if tag=="script":
            self._inside_script=True
            if "src" in d: self.asset_sources.append(d["src"])
        if tag in ("img","link","iframe","object","embed") and "src" in d:
            self.asset_sources.append(d["src"])
        if tag in ("input","button","form"):
            self.inputs.append((tag,d))

    def handle_endtag(self,tag):
        if tag=="script": self._inside_script=False

    def handle_data(self,data):
        if self._inside_script:
            self.inline_scripts.append(data)


class OfflineNonphysicalSchematicViewerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # One unmocked original source/owner offline checking + topology
        # pass is required before any input-attack test fixture.
        cls.baseline=viewer.contract()
        cls.html=viewer.render_html()

    def copy(self):
        return deepcopy(self.baseline)

    def exact(self,doc):
        with mock.patch.object(viewer,"contract",return_value=self.copy()):
            return viewer.assert_exact_source_bound(doc)

    def refusal(self,doc):
        with self.assertRaises(viewer.SchematicRefusal):
            self.exact(doc)

    def test_true_original_path_is_source_derived_not_physical(self):
        x=self.copy()
        self.assertEqual(x["status"],viewer.STATUS)
        self.assertEqual(x["schema"],viewer.SCHEMA)
        self.assertEqual(x["sourceReviewHead"],viewer.SOURCE_CI_COMMIT)
        self.assertEqual(x["diagramUnits"],viewer.DECLARED_UNITS)
        self.assertEqual(x["layoutPurpose"],"topological_reading_order_only")
        self.assertIsNone(x["physicalLengthScale"])
        self.assertIsNone(x["physicalApparatusGeometry"])
        self.assertIs(x["physicalCoordinatesKnown"],False)
        self.assertEqual(x["sourceConnectCount"],8)
        self.assertEqual(x["sourceExactPortCount"],12)
        self.assertEqual(len(x["schematicJunctions"]),4)
        self.assertEqual(len(x["schematicOrientedRods"]),4)
        self.assertTrue(self.exact(x))

    def test_source_path_owner_order_is_unique_and_just_a_reading_order(self):
        d=self.baseline
        expected=["hotBath","leftBuffer","rightBuffer","coldBath"]
        by_id={n["id"]:n["label"] for n in d["schematicJunctions"]}
        self.assertEqual([by_id[x] for x in d["sourceJunctionOrder"]],expected)
        self.assertEqual(
            [n["diagramX"] for n in sorted(d["schematicJunctions"],
                                           key=lambda n:n["diagramX"])],
            [132,382,632,882])
        self.assertEqual({n["diagramY"] for n in d["schematicJunctions"]},{218})
        for n in d["schematicJunctions"]:
            self.assertIsNone(n["nativeTemperature"])
            self.assertEqual(n["nativeStatus"],"not_computed")

    def test_parallel_rods_get_two_clearly_nonphysical_diagram_lanes(self):
        d=self.baseline
        by={r["name"]:r for r in d["schematicOrientedRods"]}
        self.assertEqual(d["sourceParallelPair"],["flatBridge","roundBridge"])
        self.assertEqual(by["flatBridge"]["fromJunctionId"],
                         by["roundBridge"]["fromJunctionId"])
        self.assertEqual(by["flatBridge"]["toJunctionId"],
                         by["roundBridge"]["toJunctionId"])
        self.assertEqual(by["flatBridge"]["diagramY"],174)
        self.assertEqual(by["roundBridge"]["diagramY"],262)
        self.assertEqual(by["flatBridge"]["expectedPositiveFlowExport"],
                         "flatBridge.Q_flow")
        for e in by.values():
            self.assertEqual(e["nativeStatus"],"not_computed")
            self.assertIsNone(e["nativeHeatFlow"])
            self.assertEqual(e["sourceOrientation"],
                             "port_a_to_port_b_not_observed_heat_direction")

    def test_original_thermal_junction_source_ports_still_visible(self):
        by={n["label"]:n for n in self.baseline["schematicJunctions"]}
        self.assertEqual(by["hotBath"]["sourcePorts"],
                         ["hotBath.port","hotLead.port_a"])
        self.assertEqual(by["coldBath"]["sourcePorts"],
                         ["coldBath.port","coldLead.port_b"])
        self.assertEqual(set(by["leftBuffer"]["sourcePorts"]),{
            "flatBridge.port_a","hotLead.port_b",
            "leftBuffer.port","roundBridge.port_a"})
        self.assertEqual(set(by["rightBuffer"]["sourcePorts"]),{
            "coldLead.port_a","flatBridge.port_b",
            "rightBuffer.port","roundBridge.port_b"})

    def test_each_public_request_has_source_derived_valid_highlight_target(self):
        doc=self.baseline
        valid={"node-"+n["id"] for n in doc["schematicJunctions"]} | {
            "rod-"+e["name"] for e in doc["schematicOrientedRods"]}
        self.assertEqual(len(valid),8)
        self.assertEqual(len(doc["publicRequestHighlights"]),9)
        for item in doc["publicRequestHighlights"]:
            with self.subTest(rid=item["id"]):
                self.assertTrue(set(item["highlightElements"])<=valid)
                self.assertTrue(item["highlightElements"])
                self.assertEqual(item["nativeStatus"],"not_computed")
                self.assertIsNone(item["nativeValue"])
        by={x["id"]:x for x in doc["publicRequestHighlights"]}
        self.assertEqual(by["leftTemperature"]["highlightElements"],
                         ["node-junction-02"])
        self.assertEqual(by["rightTemperature"]["highlightElements"],
                         ["node-junction-01"])
        self.assertEqual(by["bufferTemperatureDifference"]["highlightElements"],
                         ["node-junction-02","node-junction-01"])
        self.assertEqual(by["hotLeadFlow"]["highlightElements"],
                         ["rod-hotLead","node-junction-03","node-junction-02"])

    def test_all_original_fields_undecoded_and_all_native_flags_false(self):
        d=self.baseline
        self.assertEqual(d["nativeObservationCount"],0)
        self.assertEqual(d["nativePublicRequestsStillNotComputed"],9)
        self.assertIsNone(d["nativePublicValues"])
        self.assertIs(d["releaseBlocked"],True)
        self.assertEqual(len(d["missingNativeReleaseGates"]),11)
        for k in viewer.FALSE_FLAGS:
            with self.subTest(k=k):
                self.assertIs(d[k],False)
        self.assertEqual(d["originalModelSha256"],
                         "9a165e5ce2cc85da84ecc8bc4e63e2990f2066f3547dc6ba8508fa1afbe5f435")
        self.assertEqual(d["approvedOfflineReferenceSeal"],
                         "d2b8e2ca8e1f929cac7b028dcc3f7d0b453921d193f877eb091e23ac70aa4ce9")

    def test_standalone_html_contains_no_untrusted_network_or_external_assets(self):
        page=self.html
        self.assertTrue(page.startswith("<!doctype html>\n"))
        self.assertIn("default-src &#x27;none&#x27;",page)
        self.assertIn("connect-src &#x27;none&#x27;",page)
        self.assertIn("object-src &#x27;none&#x27;",page)
        self.assertIn("base-uri &#x27;none&#x27;",page)
        self.assertIn('script-src &#x27;sha256-',page)
        self.assertNotIn("http://",page)
        self.assertNotIn("https://",page)
        for forbidden in ("fetch(","XMLHttpRequest","WebSocket(",
                          "document.cookie","localStorage","eval(","<iframe",
                          "<img","<canvas","<form","<link","src="):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden,page)
        self.assertIn("ALL NINE NATIVE READINGS NOT COMPUTED",page)
        self.assertIn("NOT TO PHYSICAL SCALE",page)
        self.assertIn("RELEASE BLOCKED",page)
        self.assertIn("not computed",page.lower())

    def test_offline_inline_script_CSP_hash_matches_exact_embedded_JS(self):
        encoded=base64.b64encode(hashlib.sha256(viewer.JS.encode()).digest()).decode()
        self.assertIn("sha256-"+encoded,self.html)
        self.assertEqual(self.html.count("<script>"),1)
        self.assertEqual(self.html.count("</script>"),1)
        self.assertEqual(self.html.count("<style>"),1)
        self.assertEqual(self.html.count("</style>"),1)
        self.assertIn('select.addEventListener("change",update)',self.html)
        self.assertIn("detail.textContent=",self.html)
        self.assertNotIn("innerHTML=",self.html)

    def test_html_has_accessible_select_nine_original_options_plus_show_all(self):
        summary=_HtmlSummary()
        summary.feed(self.html)
        self.assertEqual(summary.asset_sources,[])
        self.assertEqual(summary.inputs,[])
        self.assertEqual(summary.tag_counts.get("svg"),1)
        self.assertEqual(summary.tag_counts.get("select"),1)
        self.assertEqual(summary.tag_counts.get("option"),10)
        self.assertEqual(summary.tag_counts.get("script"),1)
        self.assertEqual(len(set(summary.ids)),len(summary.ids))
        self.assertIn("topology-schematic",summary.ids)
        self.assertIn("public-request",summary.ids)
        self.assertIn("request-detail",summary.ids)
        self.assertEqual(summary.options[0]["value"],"")
        for d in summary.options[1:]:
            self.assertEqual(len(d["data-focus"].split(",")),
                             len(set(d["data-focus"].split(","))))
            self.assertIn("NOT COMPUTED",d["data-summary"])
        self.assertEqual([o["value"] for o in summary.options[1:]],
                         [r["id"] for r in self.baseline["publicRequestHighlights"]])

    def test_svg_parses_and_contains_only_schematic_nodes_rods(self):
        match=re.search(r'<svg\b[^>]*>.*?</svg>',self.html,re.S)
        self.assertIsNotNone(match)
        root=ET.fromstring(match.group())
        ns={"s":"http://www.w3.org/2000/svg"}
        # HTML inline SVG defaults to an unnamespaced XML view, which the
        # XML parser can inspect without using a browser or executing JS.
        # The SVG root tag itself ends in "g": do not count it as a <g>.
        groups=[g for g in root.iter()
                if g.tag=="g" or g.tag.endswith("}g")]
        self.assertEqual(len(groups),8)
        self.assertEqual(sum(x.attrib.get("class")=="node" for x in groups),4)
        self.assertEqual(sum(x.attrib.get("class")=="rod" for x in groups),4)
        self.assertEqual(len([e for e in root.iter() if e.tag.endswith("line")]),4)
        self.assertEqual(len([e for e in root.iter() if e.tag.endswith("circle")]),4)
        self.assertIn('viewBox="0 0 1060 390"',match.group())
        self.assertNotIn("nativeValue",match.group())
        self.assertNotIn("temperature=293",match.group())

    def test_text_escaping_is_safe_for_untrusted_labels_even_if_mistakenly_passed(self):
        bad='<script>alert("nativeApproved")</script>'
        escaped=viewer._text(bad)
        self.assertNotIn("<script>",escaped)
        self.assertIn("&lt;script&gt;",escaped)
        self.assertIn("&quot;",escaped)
        self.assertNotIn("</script>",escaped)

    def test_string_expression_is_only_sign_labels_not_math_evaluation(self):
        by={r["id"]:r for r in self.baseline["publicRequestHighlights"]}
        self.assertEqual(viewer._term_label(
            by["bufferTemperatureDifference"]["expectedExportTerms"]),
            "leftBuffer.T − rightBuffer.T")
        self.assertEqual(viewer._term_label(
            by["hotLeadFlow"]["expectedExportTerms"]),"hotLead.Q_flow")
        self.assertIn("leftBuffer.T − rightBuffer.T",self.html)

    def test_native_observation_or_owner_permission_mutations_always_refused(self):
        for k in viewer.FALSE_FLAGS:
            for value in (True,0,0.0):
                x=self.copy();x[k]=value
                with self.subTest(k=k,value=repr(value)):
                    self.refusal(x)
        for k,value in (("nativeObservationCount",1),
                        ("nativePublicRequestsStillNotComputed",0),
                        ("releaseBlocked",False),
                        ("nativePublicValues",{})):
            x=self.copy();x[k]=value
            with self.subTest(k=k):self.refusal(x)

    def test_physical_coordinates_geometry_and_diagram_units_forgery_refuse(self):
        cases=(
            ("physicalLengthScale",1.0),
            ("physicalApparatusGeometry",{"tubeWidth":0.05}),
            ("physicalCoordinatesKnown",True),
            ("diagramUnits","meters"),
            ("layoutPurpose","actual_apparatus_geometry"),
        )
        for k,val in cases:
            x=self.copy();x[k]=val
            with self.subTest(k=k):self.refusal(x)
        for k,val in (("diagramX",1.5),("diagramY",True),
                      ("nativeTemperature",300.15)):
            x=self.copy();x["schematicJunctions"][0][k]=val
            self.refusal(x)

    def test_source_node_order_or_parallel_geometry_spoof_refused(self):
        variants=[]
        x=self.copy();x["sourceJunctionOrder"].reverse();variants.append(x)
        x=self.copy();x["sourceJunctionOrder"][1]="junction-99";variants.append(x)
        x=self.copy();x["schematicJunctions"][0]["label"]="fakeBath";variants.append(x)
        x=self.copy();x["schematicJunctions"][0]["diagramX"]=1234;variants.append(x)
        x=self.copy();x["sourceParallelPair"].reverse();variants.append(x)
        x=self.copy();x["schematicOrientedRods"][0]["diagramY"]=230;variants.append(x)
        x=self.copy();x["schematicOrientedRods"][0]["nativeHeatFlow"]=5.0;variants.append(x)
        x=self.copy();x["schematicOrientedRods"][0]["sourceOrientation"]="native_positive_flow";variants.append(x)
        for i,v in enumerate(variants):
            with self.subTest(i=i):self.refusal(v)

    def test_request_focus_and_text_sign_forgery_refused(self):
        variants=[]
        x=self.copy();x["publicRequestHighlights"][0]["highlightElements"]=["node-junction-99"];variants.append(x)
        x=self.copy();x["publicRequestHighlights"][0]["unit"]="W";variants.append(x)
        x=self.copy();x["publicRequestHighlights"][0]["nativeValue"]=0;variants.append(x)
        x=self.copy();x["publicRequestHighlights"][0]["nativeStatus"]="computed";variants.append(x)
        x=self.copy();x["publicRequestHighlights"][6]["expectedExportTerms"][1]["sign"]=1;variants.append(x)
        x=self.copy();x["publicRequestHighlights"].reverse();variants.append(x)
        for i,v in enumerate(variants):
            with self.subTest(i=i):self.refusal(v)

    def test_missing_or_changed_original_science_source_native_gate_refused(self):
        for k,value in (
            ("originalModelSha256","f"*64),
            ("modalStudySha256","f"*64),
            ("approvedOfflineReferenceRawSha256","f"*64),
            ("approvedOfflineReferenceSeal",
             "c30e8783d39c7b0198c1adf0273ac84568f698f08287f02bf79eeed224830b07"),
            ("sourceReviewHead","0"*40),
        ):
            x=self.copy();x[k]=value
            with self.subTest(k=k):self.refusal(x)
        x=self.copy();x["missingNativeReleaseGates"].pop();self.refusal(x)
        x=self.copy();x["missingNativeReleaseGates"][0]="claimedSigned";self.refusal(x)

    def test_model_path_fork_or_split_brain_adversarially_refused(self):
        d=self.baseline
        # Exercise the pre-layout helper using its ORIGINAL input schema,
        # not the already-rendered schematic's compact label schema.
        originals=[{"id":n["id"],"owningComponent":n["label"]}
                   for n in d["schematicJunctions"]]
        rods=deepcopy(d["schematicOrientedRods"])
        good=viewer._path_from_source(originals,rods)
        self.assertEqual(good,d["sourceJunctionOrder"])
        rods[1]["toJunctionId"]="junction-00"
        with self.assertRaises(viewer.SchematicRefusal):
            viewer._path_from_source(originals,rods)

    def test_full_integrated_source_render_never_calls_native_or_reference_generator(self):
        with mock.patch.object(reference,"prepare",side_effect=AssertionError(
                 "regenerating original PR31 saved reference forbidden")), \
             mock.patch.object(matv4,"decode_mat_file",side_effect=AssertionError(
                 "MAT result decoding forbidden")), \
             mock.patch.object(h1_native_batch,"prepare",side_effect=AssertionError(
                 "original native runner.prepare forbidden")), \
             mock.patch.object(h1_native_batch,"execute",side_effect=AssertionError(
                 "native model launch forbidden")), \
             mock.patch.object(h1_native_batch,"invoke",side_effect=AssertionError(
                 "any original native subprocess forbidden")):
            doc=viewer.contract()
            page=viewer.render_html()
        self.assertEqual(doc["nativeObservationCount"],0)
        self.assertIn("NOT COMPUTED",page)
        self.assertTrue(doc["releaseBlocked"])

    def test_only_two_offline_descriptive_cli_actions(self):
        with mock.patch.object(viewer,"contract",return_value=self.copy()), \
             mock.patch("builtins.print"):
            self.assertEqual(viewer.main(["describe-nonphysical-layout-only"]),0)
        with mock.patch.object(viewer,"render_html",return_value=self.html), \
             mock.patch("builtins.print"):
            self.assertEqual(viewer.main(["print-offline-html-only"]),0)
        for op in ("native","omc","execute","approve","build","launch",
                   "generate-native","reserve-native","read-mat","install"):
            with self.subTest(op=op),mock.patch("sys.stderr"):
                with self.assertRaises(SystemExit) as exc:
                    viewer.main([op])
                self.assertEqual(exc.exception.code,2)


if __name__=="__main__":
    unittest.main()
