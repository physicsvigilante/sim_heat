# Connect a star and a triangle at one free junction

Take the [three-terminal assemblies](../three_terminal/README.md). Disconnect the reservoir at the star's middle terminal and the reservoir at the triangle's warm terminal. Bring the two exposed terminals into perfect thermal contact. The remaining baths stay at 380 K and 280 K on the left and at 330 K and 280 K on the right. The two 280 K baths are separate physical ports.

At steady state the contact takes a common temperature and the sum of the two heat supplies there is zero. With the left star replaced by its equivalent triangle, the new contact sees conductances of 0.6, 1.5, 0.6 and 1 W/K to the four baths respectively. Its temperature is (0.6×380 + 1.5×280 + 0.6×330 + 1×280)/3.7 = 11260/37 K, about 304.32 K. The former maintained contact temperatures have no influence once their reservoirs are removed.

The independent full assembly retains all six rods. Each has length 0.1 m and area 0.01 m². Left leg conductivities are 20, 30 and 50 W/(m·K); right triangle conductivities are 6, 10 and 15 W/(m·K), in the same order as the component studies. Both the original star centre and the new contact are ideal, storage-free nodes.

The reduced calculation obtains two source-pinned terminal laws and imposes conservation at the common port. Its four-terminal response, four signed heat supplies and junction temperature can be checked against the explicit assembly with `python -B -m unittest -v tests.test_join_thermal_networks`. The CLI `python -B -m tools.join_thermal_networks --help` lists the source inputs and port choices. Each side operates in the steady, linear conduction domain of the terminal-response tool.
