"""Bundling experiment: 16 issues, each with two opposite statements, each matched to one General Social Survey (GSS) item.

Statement A of every issue is the survey answer coded 1 in `GSS[issue]`; statement B is the opposite answer. The order
of the issues and of A/B says nothing about left or right, and no left/right tag exists anywhere in the bundling code.
Jev only ever sees pairs of these sentences.

GSS recodes (variable, values that mean A, values that mean B; anything else is dropped as missing/middle):
"""
ISSUES = [
 ("guns", "gunlaw", [1], [2],
  "A police permit should be required before anyone can buy a gun.",
  "People should be able to buy a gun without needing a police permit."),
 ("death penalty", "cappun", [1], [2],
  "The death penalty is right for people convicted of murder.",
  "The death penalty should not be used, even for murder."),
 ("abortion", "abany", [1], [2],
  "A woman should be able to get a legal abortion for any reason.",
  "Abortion should not be legal just because a woman wants one."),
 ("marijuana", "grass", [1], [2],
  "Marijuana should be legal.",
  "Marijuana should stay illegal."),
 ("environment", "natenvir", [1], [2, 3],
  "The government spends too little on protecting the environment.",
  "The government already spends enough, or too much, on the environment."),
 ("inequality", "eqwlth", [1, 2, 3], [5, 6, 7],
  "The government should reduce income differences between rich and poor.",
  "The government should not try to reduce income differences between rich and poor."),
 ("health care", "helpsick", [1, 2], [4, 5],
  "It is the government's job to help people pay their doctor and hospital bills.",
  "People should pay their own doctor and hospital bills without help from the government."),
 ("immigration", "letin1a", [4, 5], [1, 2, 3],
  "The number of immigrants coming to this country should be reduced.",
  "The number of immigrants coming to this country should stay the same or increase."),
 ("courts", "courts", [2], [1],
  "Courts are not harsh enough with criminals.",
  "Courts are too harsh with criminals."),
 ("euthanasia", "letdie1", [1], [2],
  "Doctors should be allowed to end the life of an incurable patient who asks them to.",
  "Doctors should never end a patient's life, even if the patient asks."),
 ("school prayer", "prayer", [2], [1],
  "Public schools should be allowed to require the Lord's Prayer or Bible readings.",
  "Public schools should not require prayers or Bible readings."),
 ("racial equality", "natrace", [1], [2, 3],
  "The government spends too little on improving the conditions of Black Americans.",
  "The government already spends enough, or too much, on improving the conditions of Black Americans."),
 ("military", "natarms", [1], [2, 3],
  "The government spends too little on the military and defense.",
  "The government already spends enough, or too much, on the military and defense."),
 ("same-sex relations", "homosex", [3, 4], [1, 2],
  "Sexual relations between two adults of the same sex are not wrong.",
  "Sexual relations between two adults of the same sex are wrong."),
 ("space", "natspac", [1], [2, 3],
  "The government spends too little on space exploration.",
  "The government already spends enough, or too much, on space exploration."),
 ("roads", "natroad", [1], [2, 3],
  "The government spends too little on highways and bridges.",
  "The government already spends enough, or too much, on highways and bridges."),
]
M = len(ISSUES)
NAMES = [i[0] for i in ISSUES]
GSS = {i[0]: (i[1], i[2], i[3]) for i in ISSUES}
# statement index: 2*issue + 0 for A, 2*issue + 1 for B
STATEMENTS = [s for i in ISSUES for s in (i[4], i[5])]
SHORT = ["Permit to buy a gun", "No gun permit", "Death penalty yes", "Death penalty no", "Abortion for any reason", "No elective abortion",
         "Legal marijuana", "Marijuana illegal", "More for environment", "Enough for environment", "Reduce income gaps", "Don't reduce income gaps",
         "Gov helps medical bills", "Pay own medical bills", "Fewer immigrants", "Same or more immigrants", "Courts too soft", "Courts too harsh",
         "Allow euthanasia", "No euthanasia", "Allow school prayer", "No school prayer", "More for Black Americans", "Enough for Black Americans",
         "More for military", "Enough for military", "Same-sex not wrong", "Same-sex wrong", "More for space", "Enough for space",
         "More for roads", "Enough for roads"]
assert len(SHORT) == len(STATEMENTS) == 2 * M
