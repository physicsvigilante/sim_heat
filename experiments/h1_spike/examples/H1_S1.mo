within;
model H1_S1
  SimHeat.FixedTemperature hot(T=SimHeat.Units.from_degC(100.0));
  SimHeat.FixedTemperature cold(T=SimHeat.Units.from_degC(0.0));
  SimHeat.RodCircular copper(
    k=SimHeat.Units.conductivityFromKcal(0.092,4184.0),
    L=0.75,
    d=SimHeat.Units.from_cm(2.0));
  SimHeat.RodCircular steel(
    k=SimHeat.Units.conductivityFromKcal(0.011,4184.0),
    L=1.25,
    d=SimHeat.Units.from_cm(2.0));
equation
  connect(hot.port, copper.port_a);
  connect(copper.port_b, steel.port_a);
  connect(steel.port_b, cold.port);
end H1_S1;
