"""Adversarial source-only thermal topology overlay: NO native or pose."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest import mock

from h1 import reference, matv4
from h1.study import load_study
from h1.model import Topology
from tools import h1_native_batch
from qualification.h1_c1.f02 import offline_topology_observation_overlay as overlay
from qualification.h1_c1.f02 import offline_expected_export_coverage as expected


class SourceThermalTopologyOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Exact original F0/PR31 source, Option A checking-only and 11 missing
        # owner-native release gates checked in the actual full source ONCE.
        cls.original=overlay.inventory()
        cls.study=load_study(overlay.ROOT/expected.STUDY,overlay.ROOT/"h1/cases")

    def baseline(self):
        return deepcopy(self.original)

    def verify(self,report):
        # For adversarial purely structural mutations, original true inventory
        # was independently source-verified in setUpClass.
        with mock.patch.object(overlay,"inventory",return_value=self.baseline()):
            return overlay.assert_exact_source_bound(report)

    def refused(self,report):
        with self.assertRaises(overlay.OverlayRefusal):
            self.verify(report)

    def test_four_junction_eight_component_original_topology(self):
        r=self.baseline()
        self.assertEqual(r["status"],overlay.STATUS)
        self.assertIs(r["releaseBlocked"],True)
        self.assertTrue(r["sourceDerivedOnly"])
        for key,n in (
            ("componentCount",8),("thermalJunctionCount",4),
            ("terminalPortCount",12),("originalConnectCount",8),
            ("orientedRodCount",4),("parallelBridgeGroupCount",1),
            ("publicRequestCount",9),("nativeObservationCount",0),
            ("nativePublicRequestsStillNotComputed",9)):
            self.assertEqual(r[key],n,key)
        self.assertIsNone(r["layout"])
        self.assertIsNone(r["physicalApparatusGeometry"])
        self.assertTrue(self.verify(r))

    def test_junctions_are_exact_frozen_port_equivalence_classes(self):
        r=self.baseline()
        originals=self.study.topology.nodes
        for idx,group in enumerate(originals):
            expected_id=f"junction-{idx:02d}"
            entry=r["thermalJunctions"][idx]
            self.assertEqual(entry["id"],expected_id)
            self.assertEqual(tuple(entry["sourcePorts"]),group)
            self.assertIsNone(entry["nativeTemperature"])
        all_ports=[p for item in r["thermalJunctions"] for p in item["sourcePorts"]]
        self.assertEqual(len(all_ports),12)
        self.assertEqual(set(all_ports),set(self.study.model.ports()))

    def test_every_source_connect_pair_is_in_one_original_junction(self):
        r=self.baseline()
        for i,entry in enumerate(r["sourceConnectWires"]):
            self.assertEqual(entry["sourceConnectIndex"],i)
            self.assertEqual((entry["fromPort"],entry["toPort"]),
                             self.study.model.connections[i])
            self.assertEqual(entry["junctionId"],
                             f"junction-{self.study.topology.node_of[entry['fromPort']]:02d}")
            self.assertEqual(self.study.topology.node_of[entry["fromPort"]],
                             self.study.topology.node_of[entry["toPort"]])

    def test_component_kinds_and_exact_port_terminals(self):
        r=self.baseline()
        self.assertEqual({i["name"] for i in r["components"]},
                         set(self.study.model.components))
        for entry in r["components"]:
            self.assertEqual(entry["kind"],
                             self.study.model.components[entry["name"]].kind)
            self.assertIs(entry["physicalPoseSpecified"],False)
            self.assertEqual(entry["nativeStatus"],"not_computed")
            for term in entry["sourcePorts"]:
                self.assertIn(term["port"],self.study.model.ports())
                self.assertEqual(term["junctionId"],
                                 f"junction-{self.study.topology.node_of[term['port']]:02d}")

    def test_all_four_source_oriented_rod_edges_and_sign_labels(self):
        r=self.baseline()
        self.assertEqual({x["name"] for x in r["orientedRodEdges"]},
                         {"hotLead","flatBridge","roundBridge","coldLead"})
        for rod in r["orientedRodEdges"]:
            name=rod["name"]
            self.assertEqual(rod["portA"],name+".port_a")
            self.assertEqual(rod["portB"],name+".port_b")
            self.assertEqual(rod["expectedPositiveFlowExport"],name+".Q_flow")
            self.assertEqual(rod["flowSignConvention"],
                             "source_port_a_to_port_b_positive")
            self.assertIsNone(rod["nativeHeatFlow"])
            self.assertEqual(rod["nativeStatus"],"not_computed")
            self.assertNotEqual(rod["fromJunctionId"],rod["toJunctionId"])

    def test_flat_and_round_bridges_are_same_original_two_junctions(self):
        r=self.baseline()
        pair=r["sourceParallelRodGroups"]
        self.assertEqual(len(pair),1)
        self.assertEqual(pair[0]["rodNames"],["flatBridge","roundBridge"])
        self.assertIs(pair[0]["topologyOnly"],True)
        self.assertIsNone(pair[0]["observedParallelHeatFlows"])
        rods={x["name"]:x for x in r["orientedRodEdges"]}
        self.assertEqual(
            (rods["flatBridge"]["fromJunctionId"],rods["flatBridge"]["toJunctionId"]),
            (rods["roundBridge"]["fromJunctionId"],rods["roundBridge"]["toJunctionId"]))

    def test_all_source_anchor_owners_are_exact_and_unique(self):
        r=self.baseline()
        self.assertEqual({x["owningComponent"] for x in r["thermalJunctions"]},
                         {"hotBath","coldBath","leftBuffer","rightBuffer"})
        self.assertEqual({x["owningKind"] for x in r["thermalJunctions"]},
                         {"Body","FixedTemperature"})
        for group in r["thermalJunctions"]:
            owner=group["owningComponent"]
            self.assertIn(owner+".port",group["sourcePorts"])

    def test_public_overlay_attaches_to_actual_source_port_rod_body(self):
        r=self.baseline()
        requests={x["id"]:x for x in r["expectedPublicRequestOverlays"]}
        self.assertEqual(len(requests),9)
        diff=requests["bufferTemperatureDifference"]["placement"]
        self.assertEqual(diff["kind"],"ordered_thermal_port_pair")
        self.assertEqual(diff["firstSourcePort"],"leftBuffer.port")
        self.assertEqual(diff["secondSourcePort"],"rightBuffer.port")
        self.assertNotEqual(*diff["junctionIds"])
        self.assertEqual(requests["hotLeadFlow"]["placement"]["kind"],
                         "oriented_source_rod")
        self.assertEqual(requests["hotLeadFlow"]["placement"]["rodName"],
                         "hotLead")
        self.assertEqual(requests["leftEnergyChange"]["placement"]["kind"],
                         "thermal_body")
        self.assertEqual(requests["leftTemperature"]["placement"]["kind"],
                         "thermal_port")
        self.assertEqual([x["id"] for x in r["expectedPublicRequestOverlays"]],
                         [x["id"] for x in self.study.data["requests"]])

    def test_no_native_values_or_geometry_ever_in_source_view_model(self):
        r=self.baseline()
        self.assertEqual(r["nativeObservationCount"],0)
        self.assertEqual(r["nativePublicRequestsStillNotComputed"],9)
        self.assertEqual(len(r["missingNativeReleaseGates"]),11)
        for key in overlay.FALSE_FLAGS:
            self.assertIs(r[key],False)
        for row in r["expectedPublicRequestOverlays"]:
            self.assertIsNone(row["nativeValue"])
            self.assertEqual(row["nativeStatus"],"not_computed")
        raw=overlay.canonical(r).decode()
        self.assertNotIn('"positions"',raw)
        self.assertNotIn('"coordinates"',raw)
        self.assertNotIn('"trajectory"',raw)
        self.assertNotIn('"model_res.mat"',raw)
        self.assertLess(len(raw),22000)

    def test_forged_native_public_value_temperature_and_heat_flow_refused(self):
        for name,value in (
            ("nativeValue",293.15),("nativeValue",0),
            ("nativeStatus","computed"),("expectedOnly",False),
        ):
            x=self.baseline();x["expectedPublicRequestOverlays"][0][name]=value
            with self.subTest(field=name,value=value):
                self.refused(x)
        for name,value in (("nativeTemperature",333.15),("nativeStatus","qualified")):
            x=self.baseline();x["thermalJunctions"][0][name]=value
            self.refused(x)
        for name,value in (("nativeHeatFlow",30.0),("nativeStatus","observed")):
            x=self.baseline();x["orientedRodEdges"][0][name]=value
            self.refused(x)

    def test_fake_layout_coordinates_geometry_and_pose_refused(self):
        for name,value in (
            ("layout",{"x":1,"y":2}),
            ("physicalApparatusGeometry",{"length":0.1}),
        ):
            x=self.baseline();x[name]=value
            with self.subTest(field=name):
                self.refused(x)
        x=self.baseline();x["components"][0]["physicalPoseSpecified"]=True
        self.refused(x)
        x=self.baseline();x["sourceConnectWires"][0]["screenX"]=100
        self.refused(x)

    def test_wrong_source_connection_ports_and_split_or_merged_junction_refused(self):
        mutations=[]
        x=self.baseline();x["sourceConnectWires"][0]["toPort"]="rightBuffer.port";mutations.append(x)
        x=self.baseline();x["sourceConnectWires"][0]["junctionId"]="junction-99";mutations.append(x)
        x=self.baseline();x["sourceConnectWires"][0],x["sourceConnectWires"][1]=(
            x["sourceConnectWires"][1],x["sourceConnectWires"][0]);mutations.append(x)
        x=self.baseline();x["thermalJunctions"][0]["sourcePorts"].pop();mutations.append(x)
        x=self.baseline();x["thermalJunctions"][0]["sourcePorts"].append(
            x["thermalJunctions"][1]["sourcePorts"][0]);mutations.append(x)
        x=self.baseline();x["thermalJunctions"][0]["owningComponent"]="hotBath";mutations.append(x)
        for i,x in enumerate(mutations):
            with self.subTest(case=i):
                self.refused(x)

    def test_wrong_rod_flow_orientation_and_parallel_bridge_refused(self):
        mutations=[]
        x=self.baseline();x["orientedRodEdges"][0]["flowSignConvention"]="port_b_to_port_a";mutations.append(x)
        x=self.baseline();x["orientedRodEdges"][0]["fromJunctionId"]="junction-97";mutations.append(x)
        x=self.baseline();x["orientedRodEdges"][0]["expectedPositiveFlowExport"]="hotLead.port_b.Q_flow";mutations.append(x)
        x=self.baseline();x["sourceParallelRodGroups"][0]["rodNames"].pop();mutations.append(x)
        x=self.baseline();x["sourceParallelRodGroups"][0]["observedParallelHeatFlows"]=[1.0,2.0];mutations.append(x)
        for i,x in enumerate(mutations):
            with self.subTest(case=i):
                self.refused(x)

    def test_missing_extra_or_duplicate_component_rod_or_source_wire_refused(self):
        for group in ("components","thermalJunctions","sourceConnectWires",
                      "orientedRodEdges","expectedPublicRequestOverlays"):
            with self.subTest(group=group):
                x=self.baseline();x[group].pop()
                self.refused(x)
                x=self.baseline();x[group][-1]=deepcopy(x[group][0])
                self.refused(x)
        x=self.baseline();x["components"].append(deepcopy(x["components"][0]))
        self.refused(x)

    def test_swapped_request_sign_or_source_field_refused(self):
        for name,value in (
            ("exportName","wrongBuffer.T"),("sign",False),
            ("sign",0),("sign",-1),("sign",1.0),
        ):
            x=self.baseline()
            x["expectedPublicRequestOverlays"][6]["orderedExpectedExportTerms"][0][name]=value
            with self.subTest(field=name,value=value):
                self.refused(x)
        x=self.baseline()
        x["expectedPublicRequestOverlays"][6]["placement"]["junctionIds"].reverse()
        self.refused(x)

    def test_forged_science_root_owner_gate_or_type_loosened_count_refused(self):
        for key,value in (
            ("originalModelSha256","f"*64),
            ("modalStudySha256","f"*64),
            ("originalSavedReferenceRawSha256","f"*64),
            ("originalSavedReferenceSeal","c30e8783d39c7b0198c1adf0273ac84568f698f08287f02bf79eeed224830b07"),
            ("nativeObservationCount",True),
            ("componentCount",8.0),
            ("nativePublicRequestsStillNotComputed",False),
            ("releaseBlocked",0),
            ("sourceDerivedOnly",1),
        ):
            x=self.baseline();x[key]=value
            with self.subTest(field=key):
                self.refused(x)
        for key in overlay.FALSE_FLAGS:
            x=self.baseline();x[key]=True
            self.refused(x)
        x=self.baseline();x["missingNativeReleaseGates"].pop()
        self.refused(x)
        x=self.baseline();x["missingNativeReleaseGates"][0]="completed"
        self.refused(x)

    def test_model_connect_endpoint_split_refuses_when_upstream_source_injected(self):
        # An unreviewed source change to connect() must never be normalized
        # into a new apparently valid visualization. Mock original sources
        # only to exercise this defensive invariant without editing physics.
        base=load_study(overlay.ROOT/expected.STUDY,overlay.ROOT/"h1/cases")
        old=list(base.model.connections)
        old[0]=(old[0][0],"rightBuffer.port")
        bad=replace(base.model,connections=tuple(old))
        altered=replace(base,model=bad)
        upstream=overlay.deps.inventory()
        with mock.patch.object(overlay,"_source",return_value=(upstream,altered)):
            with self.assertRaises(overlay.OverlayRefusal):
                overlay.inventory()

    def test_no_reference_generator_native_runner_or_mat_decoder(self):
        with mock.patch.object(reference,"prepare",side_effect=AssertionError(
                 "regenerating reviewed PR31 reference forbidden")), \
             mock.patch.object(matv4,"decode_mat_file",side_effect=AssertionError(
                 "native MAT decoding forbidden")), \
             mock.patch.object(h1_native_batch,"prepare",side_effect=AssertionError(
                 "frozen native runner preparation forbidden")), \
             mock.patch.object(h1_native_batch,"execute",side_effect=AssertionError(
                 "native launch forbidden")), \
             mock.patch.object(h1_native_batch,"invoke",side_effect=AssertionError(
                 "native subprocess forbidden")):
            result=overlay.inventory()
        self.assertEqual(result["status"],overlay.STATUS)
        self.assertEqual(result["nativeObservationCount"],0)

    def test_only_offline_viewdata_cli_accepted(self):
        with mock.patch.object(overlay,"inventory",return_value=self.baseline()), \
             mock.patch("builtins.print"):
            self.assertEqual(overlay.main(["describe-source-topology-only"]),0)
        for cmd in ("native","build","launch","approve","execute","omc",
                    "render-physical-geometry","run","qualify","reserve-native"):
            with self.subTest(cmd=cmd),mock.patch("sys.stderr"):
                with self.assertRaises(SystemExit) as ctx:
                    overlay.main([cmd])
                self.assertEqual(ctx.exception.code,2)


if __name__=="__main__":
    unittest.main()
