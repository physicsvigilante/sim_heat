model H1T1_S
  // Three ideal thermostats: nodes H, C and G.
  SimHeat.FixedTemperature S_Hot(T=386);
  SimHeat.FixedTemperature S_Cold(T=294);
  SimHeat.FixedTemperature S_Guard(T=326);

  // port_a / port_b orientation follows the locked node table exactly.
  SimHeat.RodArea S01(k=125, L=0.36, A=0.00018);
  SimHeat.RodArea S02(k=80, L=0.24, A=0.00024);
  SimHeat.RodArea S03(k=205, L=0.48, A=0.00012);
  SimHeat.RodArea S04(k=42, L=0.18, A=0.0003);
  SimHeat.RodArea S05(k=64, L=0.32, A=0.0002);
  SimHeat.RodArea S06(k=180, L=0.50, A=0.00015);
  SimHeat.RodArea S07(k=30, L=0.25, A=0.0002);
  SimHeat.RodCircular S08(k=16, L=0.20, d=0.018);
equation
  // H: S_Hot.port, S01.port_a, S02.port_a
  connect(S_Hot.port, S01.port_a);
  connect(S_Hot.port, S02.port_a);

  // C: S_Cold.port, S06.port_b, S08.port_b
  connect(S_Cold.port, S06.port_b);
  connect(S_Cold.port, S08.port_b);

  // G: S_Guard.port, S07.port_b
  connect(S_Guard.port, S07.port_b);

  // J_North: ownerless, storage-free ideal junction
  connect(S01.port_b, S03.port_a);
  connect(S01.port_b, S04.port_a);
  connect(S01.port_b, S07.port_a);

  // J_South: ownerless, storage-free ideal junction
  connect(S02.port_b, S03.port_b);
  connect(S02.port_b, S05.port_a);
  connect(S02.port_b, S08.port_a);

  // J_Center: ownerless, storage-free ideal junction
  connect(S04.port_b, S05.port_b);
  connect(S04.port_b, S06.port_a);
end H1T1_S;
