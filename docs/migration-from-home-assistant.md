# Migration from Home Assistant

Deploy AirSpace beside Home Assistant, complete browser onboarding for each viewer, reproduce the
old radius and altitude choices in friendly settings, verify status and notifications, then remove
the HACS integration. AirSpace never reads HA config entries, entities, `/config/www/community`, or
the HA database. No automatic conversion is offered because old entity state is not an identity or
privacy boundary. Keep the original integration only for rollback until users confirm the new app.
