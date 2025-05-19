// Jenkins pipeline to test Terraform modules from a base version to a list of versions to check what changes/errors occur.
// Assumptions:
// - The module is hosted in a Git repository.
// - The module has examples/ contains an example usage of the module.
// - The module is published in with git tags, containing correct example usage per that version in the examples/ directory. (Ensures deploying base version is possible)

properties([
  parameters([    
    string(name: 'MODULE_NAME', defaultValue: 'module-instance-builder', description: 'Name of the module.'),
    string(name: 'PROVIDER', defaultValue: 'aws', description: 'Provider of module.'),
    string(name: 'GIT_REPO_URL', defaultValue: 'git@github.com:itsphoebe/terraform-aws-instance-builder.git', description: 'Git repository URL to clone. (e.g., git@github.com:itsphoebe/terraform-aws-module-example.git)'),
    string(name: 'GIT_BRANCH', defaultValue: 'main', description: 'Git branch to clone.'),
    string(name: 'BASE_VERSION', defaultValue: '', description: 'Version to test against (e.g., 0.1.0).'),
    string(name: 'MODULE_VERSIONS', defaultValue: '', description: 'Single or comma-separated list of module versions to test upgrading to (e.g., 0.1.1, 0.1.2, 0.2.0, 0.3.0, 0.4.0).')
  ])
])

node {
  // Groovy variables
  def tfeURL = 'https://tfe-migrate-from.phoebe-lee.sbx.hashidemos.io'
  def organization = 'phoebe-test'
  def CSV_REPORT = 'module_upgrade_results.csv'
  def versions = MODULE_VERSIONS.split(',').collect { it.trim() }

  // All parmeters are required, validate they are not empty
  script {
    def requiredParams = [
      'MODULE_NAME': MODULE_NAME,
      'BASE_VERSION': BASE_VERSION,
      'MODULE_VERSIONS': MODULE_VERSIONS,
      'PROVIDER': PROVIDER,
      'GIT_REPO_URL': GIT_REPO_URL,
      'GIT_BRANCH': GIT_BRANCH
    ]
    requiredParams.each { paramName, paramValue ->
      if (!paramValue?.trim()) {
        error "Parameter '${paramName}' is required and cannot be empty."
      }
    }
  }

  stage('Clean') {
    cleanWs()
  }

  // Validate module versions are published in the registry
  stage('Check Module Versions in Registry') {
    // Get module versions from the registry
    def response = ''
    withCredentials([string(credentialsId: 'TFE-migrate-from-admin-token', variable: 'TFE_API_TOKEN')]) {
      script {
        response = sh(
          script: '''
            curl -sS --write-out "%{http_code}" --request GET \
              --url ''' + tfeURL + '''/api/registry/v1/modules/''' + organization + '''/${MODULE_NAME}/${PROVIDER}/versions \
              --header "Authorization: Bearer $TFE_API_TOKEN" \
          ''',
          returnStdout: true
        ).trim()
        def httpCode = response.substring(response.length() - 3)
        // Fail if version does not exist
        if (httpCode != '200') {
          error "Error retrieving module ${MODULE_NAME} versions from registry. HTTP Response Code: ${httpCode}"
        }
      }
    }
    def versionCheck = [BASE_VERSION] + versions
    // Loop through each version and check if in response
    versionCheck.each { version ->
      if (!response.contains("\"version\":\"${version}\"")) {
        error "Module version ${version} does not exist in the registry."
      }
      echo "Module version ${version} exists in the registry."
    }
  }

  stage('Checkout Module Repository') {
    // Checkout based on tags. examples/ contains correct arguments for module version provided
    checkout([$class: 'GitSCM', branches: [[name: "refs/tags/${BASE_VERSION}"]],  userRemoteConfigs: [[credentialsId: 'github', url: params.GIT_REPO_URL]]])
    
    // Headers for CSV report
    // Fill first line with module name and base version that is applied
    sh """
      echo "Module,Version,Status,Deprecation/Error,Create,Destroy,Update" >> ${CSV_REPORT}
      echo "${MODULE_NAME},${BASE_VERSION},BASE VERSION APPLIED" >> ${CSV_REPORT}
    """
  
  }

  // Checkout scripts used for this pipeline into subdirectory: scripts/
  stage('Checkout Scripts Repository') {
    checkout([$class: 'GitSCM', branches: [[name: "*/main"]], userRemoteConfigs: [[credentialsId: 'github', url: "git@github.com:itsphoebe/module-upgrade-tester.git"]], extensions: [[$class: 'RelativeTargetDirectory', relativeTargetDir: 'scripts']]])
  }
  
  stage('Update Module Version to base version') {
    // Update the module version in the main.tf file using replace_version.py script
    // Assumes examples/main.tf has correct arugments for module version provided
    script {
      def output = sh(
        script: """
          python3 scripts/replace_version.py examples/main.tf ${MODULE_NAME} ${BASE_VERSION}
        """,
        returnStdout: true
      ).trim()
      echo "Output: ${output}"
    }
  }
  try {
    stage('Apply Terraform module with base version') {
      // Assumes examples directory contains an example usage of module
      // Create terraform.tf file containing details to map to an emphemeral workspace to deploy the module
      sh """
        cd examples
        cat <<EOF > terraform.tf
terraform {
  cloud {
    hostname = "${tfeURL.substring(8)}"
    organization = "${organization}"

    workspaces {
      name = "module-upgrade-tester"
    }
  }
}
EOF
      """

      // Apply module as described in examples directory
      // Failure of init or apply will fail pipeline
      sh """
        cd examples
        terraform init -no-color || exit 1
        terraform apply -no-color -auto-approve || exit 1
      """
    }


    // Loop through each version and test upgrade
    versions.each { version ->
      stage("Test Module Version ${version}") {
        echo "Testing module version: ${version}"
        def output = sh(
          script: """
            python3 scripts/replace_version.py examples/main.tf ${MODULE_NAME} ${version}
          """,
          returnStdout: true
        ).trim()
        echo "Output: ${output}"

        // Fails stage if init or plan fails, Build result is UNSTABLE
        // If plan output contains Warnings, Errors, or planned actions, error to trigger plan_extractor.py script to extract output
        // Plan must be performed to see changes of module versions
        catchError(buildResult: 'UNSTABLE', stageResult: 'FAILURE', message: "Changes found when upgrading to version ${version}") {
          try {
            sh """
              cd examples
              terraform init -upgrade -no-color
              terraform plan -detailed-exitcode -no-color 2>&1 | tee terraform_plan_output.log
              if grep -E -q "Warning:|Error:|Terraform will perform the following actions:" terraform_plan_output.log; then
                echo "Warnings, Errors, or planned actions found in terraform plan."
                exit 1
              fi
              echo "${MODULE_NAME},${version},SUCCESS" >> ../${CSV_REPORT}
            """
          } catch (Exception e) {
            // Run script to extract plan output to CSV
            sh "python3 scripts/plan_extractor.py examples/terraform_plan_output.log ${CSV_REPORT} ${MODULE_NAME} ${version}"
            error("Extracted plan output to CSV.")
          }
        }
      }

    }
      
  } finally {
    // Archive the CSV report
    stage('Archive Results') {
      archiveArtifacts artifacts: CSV_REPORT, allowEmptyArchive: true
    }

    // Destroy the base version module deployed to test upgrades
    stage('Destroy') {
      script {
        // Revert module version in examples/main.tf file to base
        def output = sh(
          script: '''
            python3 scripts/replace_version.py examples/main.tf ${MODULE_NAME} ${BASE_VERSION}
          ''',
          returnStdout: true
        ).trim()
        echo "Output: ${output}"
      }
      sh """
        cd examples
        echo "Destroying Terraform resources..."
        terraform init -upgrade -no-color
        terraform destroy -auto-approve -no-color
      """
    }
    
    stage('Clean') {
      cleanWs()
    }
  }
}