from marketplace_learning_to_rank.experiments.harness import Event,ExperimentConfig,ExperimentStore
import pytest

def test_assignment_persists_and_event_is_idempotent(tmp_path):
    store=ExperimentStore(tmp_path/'events.sqlite3')
    config=store.create(ExperimentConfig(experiment_id='test-abc',experiment_name='Persistent assignment test',experiment_salt='stable-salt-1234'))
    variant=store.assignment(config,'visitor-1')
    assert store.assignment(config,'visitor-1')==variant
    event=Event(event_id='event-0001',experiment_id=config.experiment_id,variant=variant,visitor_id='visitor-1',strategy='rules',event_type='results_exposed',source='simulated')
    assert store.event(event) is True
    assert store.event(event) is False
    assert len(store.events(config.experiment_id,'simulated'))==1

def test_reset_simulation_preserves_real_assignments_and_events(tmp_path):
    store=ExperimentStore(tmp_path/'events.sqlite3')
    config=store.create(ExperimentConfig(experiment_id='test-reset',experiment_name='Simulation reset test',experiment_salt='stable-salt-1234'))
    real_variant=store.assignment(config,'real-visitor')
    unexposed_real_variant=store.assignment(config,'unexposed-real-visitor')
    simulated_variant=store.assignment(config,'sim-visitor-000001',source='simulated')
    store.event(Event(event_id='real-event-0001',experiment_id=config.experiment_id,variant=real_variant,visitor_id='real-visitor',strategy='rules',event_type='results_exposed',source='real'))
    store.event(Event(event_id='sim-event-0001',experiment_id=config.experiment_id,variant=simulated_variant,visitor_id='sim-visitor-000001',strategy='rules',event_type='results_exposed',source='simulated'))
    store.reset_simulation(config.experiment_id)
    assert store.assignment(config,'real-visitor')==real_variant
    assert store.assignment(config,'unexposed-real-visitor')==unexposed_real_variant
    assert store.events(config.experiment_id,'real')==[('control' if real_variant=='control' else 'treatment','real-visitor','results_exposed')]
    assert store.events(config.experiment_id,'simulated')==[]

def test_experiment_strategies_must_differ():
    with pytest.raises(ValueError,match='must differ'):
        ExperimentConfig(experiment_id='same-strategy',experiment_name='Same strategy test',experiment_salt='stable-salt-1234',control_strategy='rules',treatment_strategy='rules')
