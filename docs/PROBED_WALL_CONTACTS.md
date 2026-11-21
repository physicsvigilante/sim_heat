# Locating imperfect contacts with one thermometer

Four panels conduct heat in series between 420 K and 270 K. Each panel has resistance 0.5 K/W. The middle joint is ideal. The first and third joints have unknown contact resistances. Heat flows steadily at 40 W, and an ideal thermometer reads 360 K at the middle joint.

The bath measurements determine the total resistance, 150/40 = 3.75 K/W. Subtracting the four panels leaves 1.75 K/W shared by the two unknown contacts. Several pairs of contacts give this same reading.

The thermometer supplies the missing observation. From the hot bath to the probe, two panels and the first contact drop 60 K. The first contact therefore has resistance 60/40 − 1 = **0.50 K/W**. From the probe to the cold bath, the drop is 90 K, so the third contact has resistance 90/40 − 1 = **1.25 K/W**. Moving the measured temperature down to 350 K at the same current would imply 0.75 and 1.00 K/W respectively.

The offline tool composes two contact-inference calculations at the measured joint. Both use the same current because the thermometer draws zero heat. Each segment can contain several source-pinned two-terminal layers and known contacts. Exactly one contact in each segment must be unknown. An imperfect probe joint would have two different face temperatures and falls outside this experiment.

For a current interval, each reported contact interval is a marginal bound. To evaluate a particular pair at one current, supply that current as both measurement limits. Combining independently chosen endpoints can describe two different currents.
