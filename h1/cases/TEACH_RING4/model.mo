within;
model TeacherRingFour
  // Source: experiments/teacher_ring4/TASK.md, illustrative fixed inputs.
  SimHeat.FixedTemperature bath(T=353.15);
  SimHeat.Body A(m=1.0, c=500.0, T_initial=303.15);
  SimHeat.Body B(m=1.5, c=600.0, T_initial=323.15);
  SimHeat.Body C(m=1.2, c=600.0, T_initial=288.15);
  SimHeat.Body D(m=2.0, c=550.0, T_initial=313.15);
  SimHeat.RodArea bathToA(k=120.0, L=0.40, A=0.001);
  SimHeat.RodArea ringAB(k=80.0, L=0.50, A=0.001);
  SimHeat.RodArea ringBC(k=100.0, L=0.50, A=0.001);
  SimHeat.RodArea ringCD(k=90.0, L=0.45, A=0.001);
  SimHeat.RodArea ringDA(k=70.0, L=0.50, A=0.001);
  SimHeat.RodArea diagonalAC(k=120.0, L=0.50, A=0.001);
equation
  connect(bath.port, bathToA.port_a);
  connect(bathToA.port_b, A.port);
  connect(A.port, ringAB.port_a);
  connect(ringAB.port_b, B.port);
  connect(B.port, ringBC.port_a);
  connect(ringBC.port_b, C.port);
  connect(C.port, ringCD.port_a);
  connect(ringCD.port_b, D.port);
  connect(D.port, ringDA.port_a);
  connect(ringDA.port_b, A.port);
  connect(A.port, diagonalAC.port_a);
  connect(diagonalAC.port_b, C.port);
end TeacherRingFour;
