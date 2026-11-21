within;
model JoinedRods
  SimHeat.FixedTemperature warmL(T=380);
  SimHeat.FixedTemperature coolL(T=280);
  SimHeat.FixedTemperature middleR(T=330);
  SimHeat.FixedTemperature coolR(T=280);
  SimHeat.RodArea legA(k=20, L=0.1, A=0.01);
  SimHeat.RodArea legB(k=30, L=0.1, A=0.01);
  SimHeat.RodArea legC(k=50, L=0.1, A=0.01);
  SimHeat.RodArea sideA(k=6, L=0.1, A=0.01);
  SimHeat.RodArea sideB(k=10, L=0.1, A=0.01);
  SimHeat.RodArea sideC(k=15, L=0.1, A=0.01);
equation
  connect(warmL.port, legA.port_a);
  connect(coolL.port, legC.port_a);
  connect(middleR.port, sideA.port_b);
  connect(middleR.port, sideC.port_a);
  connect(coolR.port, sideB.port_b);
  connect(coolR.port, sideC.port_b);
  connect(legA.port_b, legB.port_b);
  connect(legA.port_b, legC.port_b);
  connect(legB.port_a, sideA.port_a);
  connect(legB.port_a, sideB.port_a);
end JoinedRods;
