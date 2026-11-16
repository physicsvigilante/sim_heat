model TwoBufferParallelBridge
  SimHeat.Body leftBuffer(m=0.25, c=500, T_initial=293.15);
  SimHeat.Body rightBuffer(m=0.30, c=600, T_initial=333.15);
  SimHeat.FixedTemperature hotBath(T=363.15);
  SimHeat.FixedTemperature coldBath(T=283.15);

  SimHeat.RodArea hotLead(k=150, L=0.10, A=0.00030);
  SimHeat.RodArea flatBridge(k=200, L=0.10, A=0.00050);
  SimHeat.RodCircular roundBridge(k=50, L=0.050, d=0.020);
  SimHeat.RodArea coldLead(k=100, L=0.10, A=0.00040);

equation
  connect(hotBath.port, hotLead.port_a);
  connect(hotLead.port_b, leftBuffer.port);
  connect(leftBuffer.port, flatBridge.port_a);
  connect(leftBuffer.port, roundBridge.port_a);
  connect(flatBridge.port_b, rightBuffer.port);
  connect(rightBuffer.port, roundBridge.port_b);
  connect(rightBuffer.port, coldLead.port_a);
  connect(coldLead.port_b, coldBath.port);
end TwoBufferParallelBridge;
