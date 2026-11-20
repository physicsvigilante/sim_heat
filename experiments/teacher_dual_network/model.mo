within;
model DualNetworkLesson
  // Illustrative constant-property, lumped H1 teaching case.
  // Two independent thermal networks; arrows are port orientation only.
  SimHeat.FixedTemperature bathHot(T=353.15);
  SimHeat.FixedTemperature bathCold(T=288.15);
  SimHeat.Body plate(m=0.65,c=500,T_initial=308.15);
  SimHeat.Body left(m=0.20,c=900,T_initial=336.15);
  SimHeat.Body right(m=0.35,c=420,T_initial=296.15);
  SimHeat.RodCircular hotFeed(k=210,L=0.30,d=0.010);
  SimHeat.RodArea seriesOne(k=60,L=0.50,A=0.00030);
  SimHeat.RodCircular seriesTwo(k=120,L=0.25,d=0.006);
  SimHeat.RodArea bypass(k=65,L=0.50,A=0.00015);
  SimHeat.RodCircular pairLink(k=160,L=0.28,d=0.008);
equation
  connect(bathHot.port,hotFeed.port_a);
  connect(hotFeed.port_b,plate.port);
  connect(plate.port,seriesOne.port_a);
  connect(seriesOne.port_b,seriesTwo.port_a);
  connect(seriesTwo.port_b,bathCold.port);
  connect(bathHot.port,bypass.port_a);
  connect(bypass.port_b,bathCold.port);
  connect(left.port,pairLink.port_a);
  connect(pairLink.port_b,right.port);
end DualNetworkLesson;
