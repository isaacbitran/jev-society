# 10 topics x 4 statements, World Values Survey style. (topic, pole) tags are for ANALYSIS ONLY; the Jev rules never see them.
# pole +1 = traditional/conservative side, -1 = secular/progressive side.
RAW = {
 "religion": (["God should be at the center of public life.", "Religious faith is essential for living a moral life."],
              ["Religion should be kept completely out of government.", "People can be perfectly moral without any religion."]),
 "gender": (["When jobs are scarce, men should have more right to a job than women.", "A young child suffers when the mother works full time."],
            ["Men and women should share housework and childcare equally.", "Women make just as good political leaders as men."]),
 "family": (["Marriage should only be between a man and a woman.", "Divorce is almost never justifiable."],
            ["Same-sex couples make just as good parents as other couples.", "Couples should be free to live together without marrying."]),
 "immigration": (["Our country should sharply limit immigration.", "Immigrants threaten our national culture."],
                 ["Immigrants enrich our culture and our economy.", "We should welcome refugees fleeing war."]),
 "economy": (["Private ownership of business should be increased.", "People who work hard should keep what they earn, so taxes should be low."],
             ["The government should reduce income differences between rich and poor.", "Big corporations have too much power and need strict regulation."]),
 "authority": (["Greater respect for authority would be a good thing.", "Children should be taught obedience above independence."],
               ["Children should be taught to think for themselves and question authority.", "Protest and civil disobedience are healthy in a democracy."]),
 "environment": (["Economic growth should take priority over protecting the environment.", "Climate rules hurt working people more than they help."],
                 ["Protecting the environment should come first, even if it slows growth.", "I would pay higher taxes to fight climate change."]),
 "nation": (["I am very proud of my nation and would fight for it.", "My country's interests come before international cooperation."],
            ["I think of myself as a citizen of the world first.", "International institutions should have more power over national governments."]),
 "crime": (["Harsher punishments are the best way to reduce crime.", "The death penalty is justified for the worst crimes."],
           ["Prisons should focus on rehabilitation, not punishment.", "The police have too much power."]),
 "life": (["Abortion is never justifiable.", "Euthanasia is never justifiable."],
          ["Abortion should be the woman's own decision.", "Terminally ill people should have the right to end their lives."]),
}
POOL, TOPIC, POLE = [], [], []
for t, (cons, prog) in RAW.items():
    for s in cons: POOL.append(s); TOPIC.append(t); POLE.append(+1)
    for s in prog: POOL.append(s); TOPIC.append(t); POLE.append(-1)

# Short labels for the viewer (same order as POOL).
SHORT_POLITICS = ["God in public life", "Faith makes morals", "Secular government", "Moral without religion",
 "Men first for jobs", "Working moms hurt kids", "Share housework equally", "Women lead as well",
 "Man-woman marriage only", "Divorce unjustifiable", "Same-sex parents equal", "Cohabit freely",
 "Limit immigration", "Immigrants threaten culture", "Immigrants enrich us", "Welcome refugees",
 "More private business", "Low taxes", "Reduce inequality", "Regulate corporations",
 "Respect authority", "Teach obedience", "Question authority", "Protest is healthy",
 "Growth over environment", "Climate rules hurt workers", "Environment first", "Pay climate taxes",
 "Proud nationalist", "Country first", "Citizen of the world", "Empower global bodies",
 "Harsher punishment", "Death penalty", "Rehabilitate prisoners", "Police too powerful",
 "Abortion never OK", "Euthanasia never OK", "Abortion is her choice", "Right to die"]

# A non-political pool: everyday life. Two contrasting pairs per topic; no left/right tags.
RAW_LIFE = {
 "food": (["Home-cooked meals with family matter more than convenience.", "Traditional recipes should be kept exactly as they were."],
          ["Trying new cuisines is one of life's great pleasures.", "Eating mostly plants is the smartest way to eat."]),
 "work": (["A steady job for life is worth more than an exciting one.", "Hard work matters more than talent."],
          ["Work should be a passion, not just a paycheck.", "Remote work is better than going to an office."]),
 "family": (["Grown children should live near their parents.", "Family dinners should be a daily ritual."],
            ["Friends can be as important as family.", "Moving far away from home builds character."]),
 "money": (["Saving for the future matters more than enjoying money now.", "Debt should be avoided at almost any cost."],
           ["Experiences are worth more than possessions.", "Money spent on travel is never wasted."]),
 "home": (["Owning a house is an essential goal in life.", "A quiet suburb is the best place to raise a family."],
          ["City life is more fulfilling than suburban life.", "Owning fewer things makes people happier."]),
 "leisure": (["Weekends are for rest, not for projects.", "Television is a perfectly good way to relax."],
             ["Weekends should be spent outdoors.", "Everyone should have a serious hobby."]),
 "technology": (["Phones are ruining real conversation.", "Children should not have smartphones before high school."],
                ["New technology mostly makes life better.", "Online friendships are just as real as offline ones."]),
 "health": (["Daily exercise is a duty, not an option.", "Sleep matters more than almost anything else for health."],
            ["A little indulgence is good for the soul.", "Stress is a normal part of a full life."]),
 "routine": (["A fixed daily routine makes people happier.", "Planning ahead beats improvising."],
             ["Spontaneity makes life worth living.", "Taking big risks is how people grow."]),
 "community": (["Knowing your neighbours is essential.", "Volunteering should be part of everyone's life."],
               ["Privacy matters more than being part of a community.", "Small talk is a waste of time."]),
}
POOL_LIFE, TOPIC_LIFE = [], []
for t, (a, b) in RAW_LIFE.items():
    for s in a + b: POOL_LIFE.append(s); TOPIC_LIFE.append(t)
SHORT_LIFE = ["Home cooking first", "Keep old recipes", "Try new cuisines", "Eat mostly plants",
 "Steady job for life", "Hard work over talent", "Work as passion", "Remote work",
 "Live near parents", "Daily family dinner", "Friends = family", "Move far away",
 "Save, don't spend", "Avoid all debt", "Experiences > things", "Travel never wasted",
 "Own a house", "Quiet suburb", "City life", "Own fewer things",
 "Weekends for rest", "TV is fine", "Weekends outdoors", "Serious hobby",
 "Phones ruin talk", "No kid smartphones", "Tech makes life better", "Online friends real",
 "Exercise is a duty", "Sleep above all", "Indulge a little", "Stress is normal",
 "Fixed routine", "Plan ahead", "Spontaneity", "Take big risks",
 "Know your neighbours", "Everyone volunteers", "Privacy over community", "Small talk is waste"]
POOLS = {"politics": POOL, "life": POOL_LIFE}
SHORT = {"politics": SHORT_POLITICS, "life": SHORT_LIFE}
TOPICS = {"politics": TOPIC, "life": TOPIC_LIFE}
assert all(len(SHORT[k]) == len(POOLS[k]) == 40 for k in POOLS)
