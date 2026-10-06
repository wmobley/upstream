# Upstream for Student Researchers

## Purpose

Introduce Upstream as a practical web interface for exploring environmental sensor data. The session should leave students able to find a project, understand the Campaign → Station → Sensor → Measurement structure, and explore spatial and temporal patterns in the UI.

## Suggested format

- **Length:** 15 minutes
- **Audience:** students who may be new to environmental data systems or time-series analysis
- **Balance:** 2 minutes of context, 11 minutes of live UI demonstration, and 2 minutes for questions
- **Core message:** Upstream keeps environmental measurements connected to their location, instrument, and time so students can explore them with confidence.

## Learning objectives

By the end of the session, students should be able to:

1. Explain the Upstream data hierarchy.
2. Find an available Upstream project after signing in.
3. Move from a campaign to a station and sensor.
4. Read a map and time-series chart well enough to ask a research question.
5. Formulate one follow-up research question from what they observe.

## Presentation outline

### 1. Opening: start with a research question (2 minutes)

Use a question students can recognize:

> How did conditions change across locations, and what evidence in the sensor record supports that conclusion?

Briefly describe the usual path from field instrument to analysis:

```text
instrument → measurements → organized project → visual exploration → analysis → shared dataset
```

Explain that Upstream helps keep the context attached to the measurements: where they came from, which instrument produced them, and when they were collected.

### 2. What Upstream contains (2 minutes)

Introduce the hierarchy with one concrete example:

```text
Campaign: a field study or monitoring effort
  Station: a fixed site or a moving collection site
    Sensor: one measurement channel, such as temperature or water level
      Measurement: one timestamped value, with location when available
```

Emphasize that a measurement without time, location, variable, and units is difficult to interpret. Upstream stores those relationships together.

### 3. How students access projects (1 minute)

Show the sign-in and project/instance selection flow. Explain that the available list depends on the student’s Tapis permissions and project allocation. Avoid presenting a hard-coded list of URLs. Point students to the project selector and the API documentation link for the selected project.

### 4. Live demo: from campaign to evidence (8 minutes)

Follow the runbook below. Keep one research question visible while navigating.

### 5. Close with a student exercise and questions (2 minutes)

Ask students to choose one station and answer:

1. What variable did the sensor measure?
2. Over what time period?
3. What spatial or temporal pattern do you see?
4. What additional information would you need before making a scientific claim?

## Live UI demo runbook

### Before students arrive

- Confirm the teaching Upstream URL and that the presenter account can sign in.
- Confirm at least one campaign has stations, sensors, a map, and enough measurements to make the chart meaningful.
- Open the web interface in advance and select the demo project.
- Test the project selector with the presenter account.
- Close unrelated tabs and disable notifications.
- Have screenshots or a short screen recording ready in case authentication, network access, or the live dataset fails.

### Demo data status

The UI repository includes bundled example files at [`upstream-ui/public/examples/data/`](../../upstream-ui/public/examples/data/):

- `sensors.csv` contains three example variables: River Stage, Rain Increment, and Flow Volume.
- `measurements.csv` contains timestamped values and coordinates near latitude `30.18611`, longitude `-93.90833`.

These files support a backup upload or explanation of the data structure, but they do not by themselves populate a live campaign. Before presenting, verify that the teaching account can open a campaign with populated station and sensor dashboards. If no live campaign is available, use prepared screenshots or create a disposable practice station in advance.

### Demo story

Use a single question such as: **“Where and when does this sensor show the strongest change?”**

1. **Sign in and select a project.** Explain that project visibility comes from Tapis access and allocations.
2. **Open a campaign.** Point out the campaign metadata, date range, and geographic context.
3. **Open the station list.** Compare a fixed station with a mobile station if both exist. Explain why a moving station can produce a track rather than one point.
4. **Open the station dashboard.** Identify the station location, summary statistics, and available sensors.
5. **Open one sensor.** Read the variable name and units before interpreting the chart.
6. **Use the time-series chart.** Change the time range, zoom into a feature, and describe gaps or changes in sampling density. If confidence bounds are present, explain that the shaded region represents uncertainty or an interval associated with the aggregated values.
7. **Use the map view.** Relate the measurement pattern to geography. For a mobile station, show how the measurement locations form a route.
8. **Ask the room for an observation.** Have students identify one visible pattern and one possible alternative explanation.

## Questions to ask during the presentation

- What does the station add that a raw CSV file does not?
- Why do units and timestamps matter before plotting a value?
- What pattern could be caused by the instrument rather than the environment?
- When would a map reveal something a time-series chart would hide?
- When would you stop using the browser and switch to a notebook or API client?

## Failure recovery

If login fails, switch to the prepared screenshots and explain the workflow using the data hierarchy. If the live project has sparse data, use the API docs and example files instead of improvising with an unrelated project. If the chart is slow, reduce the time range and explain that large sensor histories may be aggregated or downsampled for interactive viewing.

## Take-home references

- [Upstream overview](../../README.md)
- [Upstream web interface README](../../upstream-ui/README.md)
- [Python SDK README](../../upstream-sdk/README.md)
- [Authentication reference](../auth/tapis-pods-auth.md)
- [WebODM integration and REST API reference](../integrations/webodm.md)

## Presenter notes

Keep implementation details in reserve. The most valuable sequence is: identify the research question, locate the data, understand its context, and inspect the pattern. Avoid implying that a visible correlation is automatically a scientific conclusion; use the demo to model careful interpretation.
