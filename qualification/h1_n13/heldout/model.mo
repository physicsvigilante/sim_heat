within;
model TwinBridge
  SimHeat.Body amber(m=0.2,c=300,T_initial=355);
  SimHeat.Body blue(m=0.15,c=400,T_initial=275);
  SimHeat.FixedTemperature bath(T=305);
  SimHeat.RodArea upper(k=100,L=0.1,A=0.002);
  SimHeat.RodArea lower(k=200,L=0.12,A=0.0012);
  SimHeat.RodArea feed(k=80,L=0.1,A=0.005);
  SimHeat.RodArea link(k=50,L=0.1,A=0.002);
equation
  connect(amber.port,upper.port_a);
  connect(amber.port,link.port_b);
  connect(blue.port,lower.port_b);
  connect(blue.port,link.port_a);
  connect(bath.port,feed.port_a);
  connect(feed.port_b,upper.port_b);
  connect(feed.port_b,lower.port_a);
end TwinBridge;
