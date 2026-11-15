within;
model DevThermalBridge
  SimHeat.FixedTemperature heated(T=353.15);
  SimHeat.FixedTemperature cooled(T=283.15);
  SimHeat.Body left(m=1.3,c=520.0,T_initial=298.15);
  SimHeat.Body right(m=1.8,c=680.0,T_initial=328.15);
  SimHeat.RodArea supplyLeft(k=80.0,L=0.4,A=0.001);
  SimHeat.RodArea supplyRight(k=40.0,L=0.5,A=0.001);
  SimHeat.RodArea rejectLeft(k=60.0,L=0.5,A=0.001);
  SimHeat.RodArea rejectRight(k=100.0,L=0.5,A=0.001);
  SimHeat.RodArea bridge(k=120.0,L=0.6,A=0.001);
equation
  connect(heated.port, supplyLeft.port_a);
  connect(supplyLeft.port_b, left.port);
  connect(heated.port, supplyRight.port_a);
  connect(supplyRight.port_b, right.port);
  connect(left.port, rejectLeft.port_a);
  connect(rejectLeft.port_b, cooled.port);
  connect(right.port, rejectRight.port_a);
  connect(rejectRight.port_b, cooled.port);
  connect(left.port, bridge.port_a);
  connect(bridge.port_b, right.port);
end DevThermalBridge;
