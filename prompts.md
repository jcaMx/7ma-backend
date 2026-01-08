### AI Capability Model

Text-based generative AI tools like ChatGPT don’t have the familiar visual interfaces found in most desktop and mobile apps. As a result, many of their capabilities remain hidden unless users know the right prompts to use. This lack of visibility can make it difficult to understand what these powerful tools can actually do—and how to make the most of them.

The **Capability Model** serves as a practical guide for exploring the wide-ranging potential of text-based AI tools like ChatGPT. It encourages a curious, experimental mindset while providing insight into the many ways generative AI can be used. Each capability reveals a different type of task the AI can help with—offering a starting point for discovering new possibilities.

## Inform

The **Inform** capability helps users quickly gather and present relevant information in response to a prompt. It can summarize large amounts of text, provide factual answers, or deliver updates on current trends. This makes it especially useful for staying up to date, conducting research, or making evidence-based decisions—without needing to dig through data manually.

#### Example tasks

- Investigating news stories, current events, or emerging trends  
- Getting answers to questions related to a field or industry  
- Researching reference sources (e.g. business, academic, scientific, medical, financial, legal, etc.)  
- Gathering background information on companies or organizations  
- Comparing products, services, tools, or methodologies  
- Finding statistics or data  
- Preparing for interviews, meetings, or presentations  
- Staying up to date on trends in a specific area


## Create & Edit

**Create & Edit** enables users to generate and refine written content. From drafting original articles to improving clarity in existing documents, this capability supports a wide range of writing tasks. With the right prompts, it can help develop creative stories, technical explanations, or even spark ideas for visual and audio content. Some platforms also support generating images, audio, or video using text inputs.

#### Example tasks

- Brainstorming creative story ideas or scripts  
- Developing outlines or drafts (e.g. reports, presentations, instructional content, etc.)  
- Writing content (e.g. articles, posts, technical documentation, help guides, etc.)  
- Drafting written communication (emails, letters, messages, etc.)  
- Creating product descriptions, marketing content, or social media content  
- Composing poetry, lyrics, or other creative writing  
- Editing or rewriting text for clarity and tone  
- Software programming or scripting  
- Creating visual content (diagrams, illustrations, photos)

## Organize

The **Organize** capability structures and categorizes information to improve clarity and usability. It can, for example, turn meeting transcripts into clear to-do lists, or group long item lists into more manageable categories. This function simplifies complex information, making it easier to understand, share, and act upon.

#### Example tasks

- Grouping similar ideas or items  
- Categorizing information for easier understanding  
- Creating outlines or structured lists  
- Turning notes or transcripts into action steps or summaries  
- Summarizing tasks or priorities from long discussions  
- Developing workflows or step-by-step processes  
- Building timelines or schedules from unstructured data  
- Mapping out content or project components  
- Creating structured reports or dashboards

## Transform

**Transform** is all about adapting and converting content into different forms. With a single prompt, it can reformat text, translate languages, summarize documents, or convert data into new structures. This makes it a versatile tool for preparing content for reports, presentations, or social media—helping users tailor their output to different audiences or formats.

#### Example tasks

- Translating content into different languages  
- Rewriting content to match a specific style or tone  
- Adapting content for different audiences or channels  
- Creating summaries or abstracts from longer texts  
- Converting lists or outlines into full text, or vice versa  
- Updating old documents to match new formats  
- Reorganizing or simplifying technical content  
- Creating diagrams (e.g. flowcharts, sequence diagrams, UML, ER diagrams)  
- Converting data between formats (e.g. JSON, CSV, XML)  
- Translating source code from one programming language to another

## Analyze

The **Analyze** capability allows users to uncover insights from text, data, or trends. It can generate pros and cons lists, comparison tables, or decision matrices. With more detailed prompts, it can also perform deeper analysis or provide thoughtful feedback—supporting strategic thinking and informed decision-making.

#### Example tasks

- Making recommendations based on evidence or reasoning  
- Seeking advice related to a specific field (medical, legal, business, etc.)  
- Weighing pros and cons of different options  
- Comparing the attributes of two or more things (products, services, tools, platforms, etc.)  
- Reviewing data to find patterns or insights  
- Summarizing feedback or survey results  
- Creating decision matrices or evaluation criteria  
- Analyzing business or project risks, performance or outcome metrics  
- Drawing conclusions from documents or reports

## Personify or Simulate

**Personify or Simulate** brings text to life by adopting a specific voice, tone, or role. It can mimic the writing style of an expert, simulate a conversation with a historical figure, or create engaging character dialogues. This capability is especially useful for training, creative writing, role-playing scenarios, or generating personalized content.

#### Example tasks

- Writing text in the voice of a specific person, role, or perspective  
- Simulating conversations with fictional or historical figures  
- Practicing interview or customer service scenarios  
- Creating personas, characters, or scenarios for use in story scripts, product design, or training material  
- Conducting user research, surveys, or interviews  
- Exploring how different types of people might respond to a situation  
- Modeling behavior or dialogue for coaching or therapy

## Explore & Guide

The **Explore & Guide** capability helps users navigate complex topics or challenges by proposing solutions and outlining action plans. Through targeted prompts, it can generate ideas, suggest next steps, and map out strategies—making it a valuable partner in brainstorming, problem-solving, and planning.

#### Example tasks

- Facilitating group planning or collaboration sessions  
- Brainstorming new ideas or solutions  
- Developing alternative approaches to a problem  
- Mapping out potential challenges or risks  
- Generating strategic options for a project or initiative  
- Breaking down complex goals into manageable steps  
- Outlining plans or roadmaps  
- Creating step-by-step guides or instructions  
- Identifying resources or tools for a task

### Bio

Take this information to create a bio that's between 150 and 200 words.

Name: {name}  
Gender: {gender}  
Title: {title}  
Company: {company}  
Biographical Material: {bio}  
Additional Notes: {notes}

---

### Audience Description

----Bio----  
{bio}

----Instructions----  
Using the content provided above, extract and summarize the following information:

1. Gender – Identify the person's gender.
2. Role – Write a concise description (100–150 words) summarizing the person’s current role and responsibilities.
3. Company – Write a concise description (100–150 words) summarizing details such as the company's industry, target audience, products, services, and partners.
4. Location – Provide the work location in the format: City, State, Country (e.g., "Los Angeles, California, USA").
5. Industry – Identify the person's industry and subcategory in the format: Category, Subcategory (e.g., "Technology, Cybersecurity").

If any detail is not explicitly stated, make a reasonable inference based on the available context.  
If a strong inference cannot be made, leave the value as an empty string ("").

----Output----  
Format the output as a JSON object using the following format:  
'''
{{
  "gender": "<Gender>",
  "role": "<Role>",
  "company": "<Company>",
  "location": "<Location>",
  "industry": "<Industry>"
}}
'''

---

### Fictional Profile

  ----Context----
  {ai_capability_model}

  {audience_description}

----Instructions----  
Using the provided context, generate a fictional professional profile that closely aligns with the original.  

Follow these rules:  
- Gender: Use the same gender as in the context.  
- Name: Generate a realistic fictional name.  
- Role: Create a different job title that is functionally similar to the original role.  
- Company: Generate a fictional company name that operates in a similar domain as the original industry.  
- Location: Choose a different city in the same country as the original location. The new city should be comparable in size, affluence, and regional importance.  

Narrative (maximum 150 words):  
- Paragraph 1: Introduce the fictional character’s name, role, and company.  
- Paragraph 2: Describe 2–3 job-related challenges that someone in this type of role may commonly face—especially those that could be addressed with support from AI Assistants.  
- Paragraph 3: Include a one-sentence summary describing how working with Digital Mixology helped the character use AI Assistants more effectively and the general impact on their work or success.

----Output----  
Output as a JSON object using the following structure:  
'''
{{
  "gender": "<Gender>",
  "name": "<Character Name>",
  "role": "<Role>",
  "company": "<Company>",
  "location": "<Location>",
  "narrative": "<Narrative>"
}}
'''

---

### Capability Scripts

  ----Context----
  {ai_capability_model}

  {audience_description}

----Instructions----  
Use the context provided above to write a series of engaging 1-minute audio scripts written in second-person narrative perspective. Each script should introduce one of the AI capabilities described in the "AI Capability Model" found in the background section.

These scripts will be converted to speech and incorporated into a slide deck aimed at helping prospective clients understand the exciting possibilities of AI—specifically how AI Assistants can support and enhance tasks relevant to their roles and workflows.

Each capability script should:
1. Write in a warm, conversational tone that feels like a supportive colleague speaking directly to the listener.
2. Provide a brief, engaging overview written in a conversational, listener-focused style, as if speaking directly to the person.
3. Vary the wording of each opening statement, but base each on a relatable scenario or moment that helps the listener instantly picture the benefit. 
4. Use vivid but simple imagery, natural phrasing, and a friendly tone that feels encouraging and accessible.
5. Mention 2–3 context-relevant tasks that an AI assistant could help streamline, automate, or enhance. Highlight not only the functional value but the emotional relief or confidence the capability provides.
6. Use a tone that is confident, approachable, and tailored to a business audience that may not have technical expertise.
7. Stay within a 1-minute read time (roughly 120 words). Use short, clear sentences that flow naturally when spoken aloud.

Guidelines:
- Use vivid, concrete examples when illustrating tasks.
- End with a forward-looking or benefit-oriented statement (e.g., “With this capability...reclaim valuable time and focus on higher-impact work.”)

----Output----  
Output as a JSON array using the following template:  
'''
[
  {{
    "capability": "<Capability>",
    "tagline": "<Tagline>",
    "script": "<Script>"
  }},
  ...
]
'''

---


### Capability Use Cases

  ----Context----
  {ai_capability_model}

  {fictional_profile}

----Instructions----  
For each of the seven capabilities previously described in "An AI Capability Model", write a series of use cases that illustrate how an AI assistant can support the role described in the character_context.

Each use case should include the following elements:
1. Capability – One of the core AI capabilities from the provided file.
2. Name – An engaging title to describe the use case; max 7 words.
3. Scenario – Present a realistic scenario with specific details of a situation, challenge, problem that prompts the use of an AI Assistant. (about 50 words)
4. Solution – Explain how the AI assistant helps address the scenario through a specific, role-relevant task and describe the response output. (about 45 words).  

Guidelines:
- Ensure that each use case is clear, realistic, and easy to understand by someone with limited technical knowledge of AI. 
- Aim to show practical value through relatable examples grounded in the responsibilities and goals of the context-described role.
- Begin the solution with a brief indication of what the character provides the AI before describing what the AI Assistant does.
- Avoid repetitively always using the characters name as the first word of the scenario and the solution. 

----Output----  
Output your response as a JSON array using the following format:  
'''
[
  {{
    "capability": "<Capability>",
    "name": "<Name>",
    "scenario": "<Scenario>",
    "solution": "<Solution>"
  }},
  ...
]
'''
