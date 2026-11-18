model H1T1_T
  // Maintained boundary nodes W and K.
  SimHeat.FixedTemperature T_Warm(T=367);
  SimHeat.FixedTemperature T_Cool(T=289);

  // Finite uniform-temperature blocks: nodes R, B and P.
  SimHeat.Body T_Ridge(m=0.32, c=460, T_initial=337);
  SimHeat.Body T_Collar(m=0.24, c=830, T_initial=303);
  SimHeat.Body T_Plug(m=0.41, c=390, T_initial=318);

  // port_a / port_b orientation follows the locked node table exactly.
  SimHeat.RodArea T01(k=65, L=0.28, A=0.00016);
  SimHeat.RodArea T02(k=45, L=0.34, A=0.00023);
  SimHeat.RodArea T03(k=180, L=0.19, A=0.0001);
  SimHeat.RodArea T04(k=25, L=0.26, A=0.00016);
  SimHeat.RodArea T05(k=42, L=0.30, A=0.00025);
  SimHeat.RodCircular T06(k=75, L=0.22, d=0.016);
  SimHeat.RodArea T07(k=120, L=0.33, A=0.00014);
  SimHeat.RodArea T08(k=20, L=0.24, A=0.00028);
  SimHeat.RodArea T09(k=16, L=0.27, A=0.00021);
  SimHeat.RodArea T10(k=95, L=0.40, A=0.00013);
equation
  // W: T_Warm.port, T01.port_a, T02.port_a
  connect(T_Warm.port, T01.port_a);
  connect(T_Warm.port, T02.port_a);

  // K: T_Cool.port, T08.port_b, T09.port_b
  connect(T_Cool.port, T08.port_b);
  connect(T_Cool.port, T09.port_b);

  // R: T_Ridge.port, T03.port_b, T04.port_a, T09.port_a
  connect(T_Ridge.port, T03.port_b);
  connect(T_Ridge.port, T04.port_a);
  connect(T_Ridge.port, T09.port_a);

  // B: T_Collar.port, T05.port_b, T06.port_a, T08.port_a
  connect(T_Collar.port, T05.port_b);
  connect(T_Collar.port, T06.port_a);
  connect(T_Collar.port, T08.port_a);

  // P: T_Plug.port, T06.port_b, T07.port_a
  connect(T_Plug.port, T06.port_b);
  connect(T_Plug.port, T07.port_a);

  // J_Upper: ownerless, storage-free ideal junction
  connect(T01.port_b, T03.port_a);
  connect(T01.port_b, T05.port_a);
  connect(T01.port_b, T10.port_a);

  // J_Lower: ownerless, storage-free ideal junction
  connect(T02.port_b, T04.port_b);
  connect(T02.port_b, T07.port_b);
  connect(T02.port_b, T10.port_b);
end H1T1_T;
