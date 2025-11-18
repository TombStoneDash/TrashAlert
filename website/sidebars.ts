import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  docsSidebar: [
    'intro',
    {
      type: 'category',
      label: 'Getting Started',
      items: [
        'guides/setup',
        'guides/quickstart',
        'guides/docker',
      ],
    },
    {
      type: 'category',
      label: 'Architecture',
      items: [
        'architecture/overview',
        'architecture/database',
        'architecture/crowdsourcing',
        'architecture/diagrams',
      ],
    },
    {
      type: 'category',
      label: 'Data Pipeline',
      items: [
        'pipeline/overview',
        'pipeline/osm-collection',
        'pipeline/address-sampling',
        'pipeline/adding-cities',
      ],
    },
    {
      type: 'category',
      label: 'Developer Guides',
      items: [
        'guides/contributing',
        'guides/testing',
        'guides/deployment',
      ],
    },
  ],
  apiSidebar: [
    'api/overview',
    {
      type: 'category',
      label: 'Endpoints',
      items: [
        'api/endpoints/lookup',
        'api/endpoints/report',
        'api/endpoints/interpret-address',
        'api/endpoints/stats',
      ],
    },
    {
      type: 'category',
      label: 'Data Models',
      items: [
        'api/models/address',
        'api/models/report',
        'api/models/consensus',
      ],
    },
    'api/examples',
    'api/errors',
  ],
};

export default sidebars;
